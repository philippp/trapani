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

# [START spanner_create_database]
# Sets up a database
def create_database(instance_id, database_id):
    """Creates a database and tables for sample data."""
    spanner_client = spanner.Client()
    instance = spanner_client.instance(instance_id)

    database = instance.database(database_id, ddl_statements=[
        """CREATE TABLE Contacts (
            Id     INT64 NOT NULL,
            Name   STRING(1024),
            PhoneNumber  STRING(100) NOT NULL
        ) PRIMARY KEY (Id)""",
        """CREATE TABLE Calls (
	Id INT64 NOT NULL,
	ConnectionStatus INT64,
	ContactIDs ARRAY<INT64> NOT NULL,
	EndCallTime TIMESTAMP,
	ProcessedTime TIMESTAMP,
	ProcessorID INT64,
	ScheduledTime TIMESTAMP NOT NULL,
) PRIMARY KEY (Id)"""
    ])

    operation = database.create()

    print('Waiting for operation to complete...')
    operation.result()

    print('Created database {} on instance {}'.format(
        database_id, instance_id))
# [END spanner_create_database]

# [START spanner_read_data]

def read_texts(instance_id, database_id, cutoff_time=None):
    if not cutoff_time:
        cutoff_time = datetime.datetime.utcnow().isoformat() + "Z"
    """Reads sample data from the database."""
    spanner_client = spanner.Client()
    instance = spanner_client.instance(instance_id)
    database = instance.database(database_id)

    pending_texts = dict()
    with database.snapshot() as snapshot:
        results = snapshot.execute_sql("""
SELECT 
  Texts.UUID, 
  ContactUUID, 
  Contacts.Name,
  Contacts.PhoneNumber,
  Texts.Message
FROM Texts
LEFT JOIN Contacts ON ContactUUID = Contacts.UUID
WHERE ScheduledTime <= @cutoff_time AND ProcessorUUID IS NULL
        """,
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
# [END spanner_read_data]

def attempt_lock_text(instance_id, database_id, text_uuid,
                      processor_uuid=None):
    return attempt_lock_entity(instance_id, database_id, text_uuid,
                        'Texts', processor_uuid=processor_uuid)
        
def attempt_lock_entity(instance_id, database_id, entity_uuid, entity_table_name,
                        processor_uuid=None):
    # DO NOT REMOVE.
    # Using string substitition of this variable in SQL below.
    assert entity_table_name in ("Texts", "Calls")
    
    spanner_client = spanner.Client()
    instance = spanner_client.instance(instance_id)
    database = instance.database(database_id)
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
    row_ct = 0
    def write_with_struct(transaction):
        row_ct = transaction.execute_update(
            ("UPDATE %s SET ProcessorUUID = @processor_uuid, "
            "ProcessStartTime = PENDING_COMMIT_TIMESTAMP()"
            "WHERE ProcessorUUID IS NULL AND UUID = @entity_uuid") % entity_table_name,
            params=params,
            param_types=param_type
        )
        print("{} record(s) updated.".format(row_ct))

    v = database.run_in_transaction(write_with_struct)
    pdb.set_trace()
    print(row_ct)
    return row_ct


def read_calls(instance_id, database_id, cutoff_time=None):
    if not cutoff_time:
        cutoff_time = datetime.datetime.utcnow().isoformat() + "Z"
    """Reads sample data from the database."""
    spanner_client = spanner.Client()
    instance = spanner_client.instance(instance_id)
    database = instance.database(database_id)

    pending_calls = dict()
    with database.snapshot() as snapshot:
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
# [END spanner_read_data]

def attempt_lock_call(instance_id, database_id, call_uuid,
                      processor_uuid=None):
    spanner_client = spanner.Client()
    instance = spanner_client.instance(instance_id)
    database = instance.database(database_id)
    if not processor_uuid:
        processor_uuid = base64.b64encode(uuid.uuid1().bytes)

    params = {
                'processor_uuid': processor_uuid,
                'call_uuid' : call_uuid
            }
    param_type = {
                'processor_uuid': param_types.BYTES,
                'call_uuid' : param_types.BYTES
    }
    row_ct = 0
    def write_with_struct(transaction):
        row_ct = transaction.execute_update(
            "UPDATE Calls SET ProcessorUUID = @processor_uuid, "
            "ProcessStartTime = PENDING_COMMIT_TIMESTAMP()"
            "WHERE ProcessorUUID IS NULL AND UUID = @call_uuid",
            params=params,
            param_types=param_type
        )
        print("{} record(s) updated.".format(row_ct))

    database.run_in_transaction(write_with_struct)
    return row_ct

def attempt_reset_call(instance_id, database_id, call_uuid,
                       processor_uuid=None):
    spanner_client = spanner.Client()
    instance = spanner_client.instance(instance_id)
    database = instance.database(database_id)

    def write_with_struct(transaction):
        row_ct = transaction.execute_update(
            "UPDATE Calls SET ProcessorUUID = NULL, ProcessStartTime = NULL "
            "WHERE UUID = @call_uuid",
            params={'call_uuid': call_uuid},
            param_types={'call_uuid': param_types.BYTES}
        )
        print("{} record(s) updated.".format(row_ct))

    database.run_in_transaction(write_with_struct)
    

def add_contact(instance_id, database_id, contact_name, contact_number):
    """Inserts a new contact.
    """
    spanner_client = spanner.Client()
    instance = spanner_client.instance(instance_id)
    database = instance.database(database_id)
    record_uuid = uuid.uuid1()
    
    with database.batch() as batch:
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

def schedule_text(instance_id, database_id, contact_number,
                  message, schedule_datetime, engagement_uuid=None):
    """Schedules a text message.
    TODO: Validate and reformat datetime and phone #"""
    if len(message) > 160:
        # TODO - log failure
        raise Exception()

    spanner_client = spanner.Client()
    instance = spanner_client.instance(instance_id)
    database = instance.database(database_id)

    # Look up the recipient
    
    recipient_uuid = None
    with database.snapshot() as snapshot:
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
    with database.batch() as batch:
        batch.insert(
            table='Texts',
            columns=columns,
            values=[values])
    pass

def schedule_call(instance_id, database_id, contact_number_list,
                  schedule_datetime, engagement_uuid=None):
    spanner_client = spanner.Client()
    instance = spanner_client.instance(instance_id)
    database = instance.database(database_id)

    # Look up the recipients
    
    recipient_uuid_list = list()
    record_type = param_types.Array(param_types.STRING)
    with database.snapshot() as snapshot:
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
        'instance_id', help='Your Cloud Spanner instance ID.')
    parser.add_argument(
        '--database-id', help='Your Cloud Spanner database ID.',
        default='example_db')

    
    subparsers = parser.add_subparsers(dest='command')
    subparsers.add_parser('create_database', help=create_database.__doc__)
    add_contact_parser = subparsers.add_parser('add_contact', help=add_contact.__doc__)
    add_contact_parser.add_argument('--name')
    add_contact_parser.add_argument('--number')
    schedule_text_parser = subparsers.add_parser('schedule_text', help=add_contact.__doc__)
    schedule_text_parser.add_argument('--message')
    schedule_text_parser.add_argument('--number')
    schedule_text_parser.add_argument('--schedule_datetime')

    schedule_call_parser = subparsers.add_parser('schedule_call', help=add_contact.__doc__)
    schedule_call_parser.add_argument('--number_a')
    schedule_call_parser.add_argument('--number_b')    
    schedule_call_parser.add_argument('--schedule_datetime')
    
    subparsers.add_parser('read_calls', help=read_calls.__doc__)
    subparsers.add_parser('read_texts', help=read_calls.__doc__)    
    
    args = parser.parse_args()

    if args.command == 'create_database':
        create_database(args.instance_id, args.database_id)
    elif args.command == 'add_contact':
        add_contact(args.instance_id, args.database_id,
                    args.name, args.number)
    elif args.command == 'read_calls':
        pprint.pprint(read_calls(args.instance_id, args.database_id))
    elif args.command == 'read_texts':
        pprint.pprint(read_texts(args.instance_id, args.database_id))
        
    elif args.command == "schedule_text":
        schedule_text(args.instance_id, args.database_id,
                      args.number, args.message, args.schedule_datetime)
    elif args.command == "schedule_call":
        schedule_call(args.instance_id, args.database_id,
                      [args.number_a, args.number_b], args.schedule_datetime)
    #gcloud spanner instances create scheduler --config=regional-us-central1     --description="Scheduler Table" --nodes=1
