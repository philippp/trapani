#!/usr/bin/env python3
"""Command line administrative tool for call and text scheduling.
"""
import pprint
import collections
import pdb
import argparse
import base64
import datetime
import uuid
from google.cloud import spanner
from google.cloud.spanner_v1 import param_types
import dateutil.parser

class Database:
    def __init__(self, instance_id, database_id):
        self.instance_id = instance_id
        self.database_id = database_id
        self.client = None

    def connect(self):
        self.client = spanner.Client()
        self.instance = self.client.instance(self.instance_id)
        self.database = self.instance.database(self.database_id)
    
    def read_texts(self, cutoff_time=None, exclude_processed=False):
        if not cutoff_time:
            cutoff_time = datetime.datetime.utcnow().isoformat() + "Z"

        sql_query = """
SELECT 
  Texts.UUID, 
  ContactUUID, 
  Contacts.Name,
  Contacts.PhoneNumber,
  Texts.Message
FROM Texts
LEFT JOIN Contacts ON ContactUUID = Contacts.UUID
WHERE ScheduledTime <= @cutoff_time
        """
        if exclude_processed:
            sql_query += " AND ProcessorUUID IS NULL"
        pending_texts = dict()
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(sql_query,
                                           params={'cutoff_time':cutoff_time},
                                           param_types={'cutoff_time' : param_types.TIMESTAMP})
            for row in results:
                pending_texts[row[0]] = {
                    'UUID' : row[0],
                    'ContactUUID' : row[1],
                    'Name' : row[2],
                    'PhoneNumber' : row[3],
                    'Message' : row[4]
                }
        return pending_texts

    def attempt_lock_text(self, text_uuid, processor_uuid=None):
        return self._attempt_lock_entity(text_uuid, 'Texts', processor_uuid=processor_uuid)

    def attempt_lock_call(self, text_uuid, processor_uuid=None):
        return self._attempt_lock_entity(text_uuid, 'Calls', processor_uuid=processor_uuid)
    
    def _attempt_lock_entity(self, entity_uuid, entity_table_name,
                            processor_uuid=None):
        # DO NOT REMOVE.
        # Using string substitition of this variable in SQL below.
        assert entity_table_name in ("Texts", "Calls")
        if not processor_uuid:
            processor_uuid = base64.b64encode(uuid.uuid1().bytes)

        params = {
            'processor_uuid': processor_uuid,
            'entity_uuid' : entity_uuid
        }
        param_type = {
            'processor_uuid': param_types.BYTES,
            'entity_uuid' : param_types.BYTES
        }
        def write_with_struct(transaction):
            row_ct = transaction.execute_update(
                ("UPDATE %s SET ProcessorUUID = @processor_uuid, "
                 "ProcessStartTime = PENDING_COMMIT_TIMESTAMP()"
                 "WHERE ProcessorUUID IS NULL AND UUID = @entity_uuid") % entity_table_name,
                params=params,
                param_types=param_type
            )
            print("{} record(s) updated.".format(row_ct))
            return row_ct

        row_ct = self.database.run_in_transaction(write_with_struct)
        return row_ct


    def read_calls(self, cutoff_time=None):
        """
        List all calls in the system.
        """
        if not cutoff_time:
            cutoff_time = datetime.utcnow().isoformat() + "Z"
        pending_calls = dict()
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql("""
SELECT 
  Calls.UUID, 
  ContactUUID, 
  Contacts.Name,
  Contacts.PhoneNumber,
  Calls.ScheduledTime
FROM Calls, UNNEST(Calls.ContactUUIDs) AS ContactUUID
LEFT JOIN Contacts ON ContactUUID = Contacts.UUID
WHERE ScheduledTime <= @cutoff_time
        """,
            params={'cutoff_time':cutoff_time},
            param_types={'cutoff_time' : param_types.TIMESTAMP})
            for row in results:
                recipient_dict = {
                    'ContactUUID' : row[1],
                    'Name' : row[2],
                    'PhoneNumber' : row[3]
                }
                if row[0] not in pending_calls:
                    pending_calls[row[0]] = {
                        'UUID':row[0],
                        'ScheduledTime':row[4],
                        'recipients': [recipient_dict]
                    }
                else:
                    pending_calls[row[0]]['recipients'].append(
                        recipient_dict)
        return pending_calls


    def add_contact(self, contact_name, contact_number):
        """Inserts a new contact.
        """
        record_uuid = uuid.uuid1()
    
        with self.database.batch() as batch:
            batch.insert(
                table='Contacts',
                columns=('UUID', 'Name', 'PhoneNumber','TimeCreated'),
                values=[
                    (
                        base64.b64encode(record_uuid.bytes),
                        contact_name,
                        contact_number,
                        spanner.COMMIT_TIMESTAMP
                    )]) 
        pass

    def schedule_text(self, contact_number, message, schedule_datetime, engagement_uuid=None):
        """Schedules a text message.
        TODO: Validate and reformat datetime and phone #"""
        if len(message) > 160:
            # TODO - log failure
            raise Exception()
        # TODO - handle DST
        dt = dateutil.parser.parse(schedule_datetime+"-07:00")
        schedule_datetime = dt.astimezone(tz=datetime.timezone.utc).isoformat()[:19]+"Z"
        print(schedule_datetime)

        # Look up the recipient
        recipient_uuid = None
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                "SELECT UUID FROM Contacts WHERE PhoneNumber = @contact_number",
                params={'contact_number': contact_number},
                param_types={'contact_number': param_types.STRING})
            if not results:
                print("Number does not exist")
                raise Exception()
            recipient_uuid = results.one()[0]
        print(recipient_uuid)
        # Schedule the message
        record_uuid = uuid.uuid1()

        columns = ["UUID", "ContactUUID", "Message", "TimeCreated", "ScheduledTime"]
        values = [
            base64.b64encode(record_uuid.bytes),
            recipient_uuid,
            message,
            spanner.COMMIT_TIMESTAMP,
            schedule_datetime
        ]
        if engagement_uuid:
            columns.append("EngagementUUID")
            values.append(engagement_uuid)
        with self.database.batch() as batch:
            batch.insert(
                table='Texts',
                columns=columns,
                values=[values])
        pass

    def schedule_call(self, contact_number_list, schedule_datetime, engagement_uuid=None):
        # Look up the recipients
    
        recipient_uuid_list = list()
        record_type = param_types.Array(param_types.STRING)
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                "SELECT UUID FROM Contacts WHERE PhoneNumber IN UNNEST(@contact_number_list)",
                params={'contact_number_list': contact_number_list},
                param_types={'contact_number_list': record_type})
            if not results:
                print("Number does not exist")
                raise Exception()
            for result in results:
                recipient_uuid_list.append(result[0])
            if not len(contact_number_list) == len(recipient_uuid_list):
                print(contact_number_list, recipient_uuid_list)
                raise Exception()

        # Schedule the call
        # Schedule the message
        record_uuid = uuid.uuid1()

        columns = ["UUID", "ContactUUIDs", "TimeCreated", "ScheduledTime"]
        values = [
            base64.b64encode(record_uuid.bytes),
            recipient_uuid_list,
            spanner.COMMIT_TIMESTAMP,
            schedule_datetime
        ]
        if engagement_uuid:
            columns.append("EngagementUUID")
            values.append(engagement_uuid)
        with database.batch() as batch:
            batch.insert(
                table='Calls',
                columns=columns,
                values=[values])
    

if __name__ == '__main__':  # noqa: C901
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--instance_id', help='Your Cloud Spanner instance ID.', default="test-instance")
    parser.add_argument(
        '--database_id', help='Your Cloud Spanner database ID.', default="phone_schedule")


    subparsers = parser.add_subparsers(dest='command')
    add_contact_parser = subparsers.add_parser('add_contact', help=Database.add_contact.__doc__)
    add_contact_parser.add_argument('--name')
    add_contact_parser.add_argument('--number')
    schedule_text_parser = subparsers.add_parser('schedule_text', help=Database.schedule_text.__doc__)
    schedule_text_parser.add_argument('--message', help="Text message to send, 160 chars max.")
    schedule_text_parser.add_argument('--number', help="Number in \"+1234567890\" format")
    schedule_text_parser.add_argument('--schedule_datetime', help="\"YYYY-MM-DDTHH:MM:SS\" In pacific time zone")

    schedule_call_parser = subparsers.add_parser('schedule_call', help=Database.schedule_call.__doc__)
    schedule_call_parser.add_argument('--number_a')
    schedule_call_parser.add_argument('--number_b')    
    schedule_call_parser.add_argument('--schedule_datetime')
    
    subparsers.add_parser('read_calls', help=Database.read_calls.__doc__)
    subparsers.add_parser('read_texts', help=Database.read_texts.__doc__)    
    
    args = parser.parse_args()

    
    db = Database(args.instance_id, args.database_id)
    db.connect()
    
    if args.command == 'add_contact':
        db.add_contact(args.name, args.number)
    elif args.command == 'read_calls':
        pprint.pprint(db.read_calls())
    elif args.command == 'read_texts':
        pprint.pprint(db.read_texts())
        
    elif args.command == "schedule_text":
        db.schedule_text(args.number, args.message, args.schedule_datetime)
    elif args.command == "schedule_call":
        db.schedule_call([args.number_a, args.number_b], args.schedule_datetime)
    #gcloud spanner instances create scheduler --config=regional-us-central1     --description="Scheduler Table" --nodes=1
