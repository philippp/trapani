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
import mysql.connector
import csv

db_info = dict(
    host='localhost',
    user='root',
    passwd='zDa1BKlkOpmmzg5n',
    database='blindchat_dev',
    port=3307
)

def execute(cursor, query, values=None):
    return cursor.execute(query, values)
    
class Database:

    def __init__(self):
        self.mysql_connection = None

    def connect(self):
        try:
            if self.mysql_connection:
                self.mysql_connection.close()
        except:
            pass
        self.mysql_connection = mysql.connector.connect(**db_info)

    def read_texts(self, cutoff_time=None, exclude_processed=False):
        if not cutoff_time:
            cutoff_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        sql_query = """
SELECT 
  texts.id as text_id, 
  contact_id, 
  contacts.name,
  contacts.phone_number,
  texts.message
FROM texts
LEFT JOIN contacts ON contact_id = contacts.id
WHERE time_scheduled <= %s
        """
        if exclude_processed:
            sql_query += " AND processor_id IS NULL"

        cursor = self.mysql_connection.cursor()
        cursor.execute(sql_query, (cutoff_time,))
        records = cursor.fetchall()
        pending_texts = dict()
        for row in records:
            pending_texts[row[0]] = {
                'id' : row[0],
                'contact_id' : row[1],
                'name' : row[2],
                'phone_number' : row[3],
                'message' : row[4]
            }
        return pending_texts
    
    def attempt_lock_text(self, text_id, processor_id=None):
        return self.attempt_lock_entity(text_id, 'texts', processor_id=processor_id)

    def attempt_lock_call(self, text_id, processor_id=None):
        return self.attempt_lock_entity(text_id, 'calls', processor_id=processor_id)
    
    def attempt_lock_entity(self, entity_id, entity_table_name,
                            processor_id=None):
        # DO NOT REMOVE.
        # Using string substitition of this variable in SQL below.
        assert entity_table_name in ("texts", "calls")
        if not processor_id:
            processor_id = uuid.uuid4().int & (1<<64)-1

        sql_query = ("UPDATE " + entity_table_name + " SET processor_id = %s, "
                     "time_dispatcher_processed = CURRENT_TIMESTAMP()"
               "WHERE processor_id IS NULL AND id = %s")
        cursor = self.mysql_connection.cursor()
        cursor.execute(sql_query, (processor_id, entity_id))
        return cursor.rowcount

    def read_calls(self, cutoff_time=None, exclude_processed=False):
        """
        List all calls in the system.
        """
        if not cutoff_time:
            cutoff_time = datetime.datetime.utcnow().isoformat() + "Z"
        pending_calls = dict()

        sql_query = """
SELECT 
  calls.id, 
  contact_a_id, 
  contact_b_id, 
  contacts_a.name as name_a,
  contacts_b.name as name_b,
  contacts_a.phone_number as number_a,
  contacts_b.phone_number as number_b,
  calls.time_scheduled
FROM calls 
LEFT JOIN contacts as contacts_a 
ON calls.contact_a_id = contacts_a.id
LEFT JOIN contacts as contacts_b
ON calls.contact_b_id = contacts_b.id
WHERE time_scheduled <= %s
        """
        if exclude_processed:
            sql_query += " AND processor_id IS NULL"

        cursor = self.mysql_connection.cursor()
        cursor.execute(sql_query, (cutoff_time,))
        records = cursor.fetchall()
        pending_calls = dict()
        for row in records:
            pending_calls[row[0]] = {
                'id' : row[0],
                'contact_a_id' : row[1],
                'contact_b_id' : row[2],
                'contact_a_name' : row[3],
                'contact_b_name' : row[4],
                'contact_a_number' : row[5],
                'contact_b_number' : row[6],
                'time_scheduled' : row[7]
            }
        return pending_calls

    def add_contacts(self, contacts):
        """Adds contacts.
        Format is {'name':contact_name, 'number':contact_number}
        """
        cursor = self.mysql_connection.cursor()
        insert_string = "INSERT INTO contacts (name, phone_number) " \
            "VALUES (%s,%s)"
        result = cursor.executemany(
            insert_string,
            [(c['name'], c['number']) for c in contacts])

    def schedule_text(self, contact_id, message, time_scheduled, engagement_id=0):
        """Schedules a text message.
        TODO: Validate and reformat datetime and phone #"""
        if len(message) > 160:
            # TODO - log failure
            raise Exception()
        # TODO - handle DST
        dt = dateutil.parser.parse(time_scheduled+"-07:00")
        time_scheduled = dt.astimezone(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(time_scheduled)

        cursor = self.mysql_connection.cursor()
        insert_string = "INSERT INTO texts (contact_id, message, time_scheduled, engagement_id) " \
            "VALUES (%s,%s, %s, %s)"
        
        cursor.execute(insert_string, (contact_id, message, time_scheduled, engagement_id))
        print("Added scheduled text #%d" % cursor.lastrowid)

    def schedule_call(self, contact_a_id, contact_b_id, time_scheduled, engagement_id=0):
        # TODO - handle DST
        dt = dateutil.parser.parse(time_scheduled+"-07:00")
        time_scheduled = dt.astimezone(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(time_scheduled)

        insert_string = "INSERT INTO calls (contact_a_id, contact_b_id, time_scheduled, engagement_id) "\
                        "VALUES (%s, %s, %s, %s)"
        values = [
            contact_a_id,
            contact_b_id,
            time_scheduled,
            engagement_id
        ]
        cursor = self.mysql_connection.cursor()        
        cursor.execute(insert_string, values)
        print("Added scheduled call #%d" % cursor.lastrowid)        
        
    

def contacts_dict_from_csv_file(contacts_csv_file):
    contacts = list()
    with open(contacts_csv_file) as csvfile:
        contactsreader = csv.reader(csvfile)
        for row in contactsreader:
            contacts.append(
                {
                    'name':row[0],
                    'number':row[1]
                })
    return contacts
            
if __name__ == '__main__':  # noqa: C901
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers(dest='command')
    add_contact_parser = subparsers.add_parser('add_contacts', help=Database.add_contacts.__doc__)
    add_contact_parser.add_argument('--contacts_csv_file', help="CSV of name, number columns")

    schedule_text_parser = subparsers.add_parser('schedule_text', help=Database.schedule_text.__doc__)
    schedule_text_parser.add_argument('--message', help="Text message to send, 160 chars max.")
    schedule_text_parser.add_argument('--user_id', help="User to schedule text for")
    schedule_text_parser.add_argument('--schedule_datetime', help="\"YYYY-MM-DDTHH:MM:SS\" In pacific time zone")

    schedule_call_parser = subparsers.add_parser('schedule_call', help=Database.schedule_call.__doc__)
    schedule_call_parser.add_argument('--contact_a_id')
    schedule_call_parser.add_argument('--contact_b_id')
    schedule_call_parser.add_argument('--schedule_datetime')
    
    subparsers.add_parser('read_calls', help=Database.read_calls.__doc__)
    subparsers.add_parser('read_texts', help=Database.read_texts.__doc__)    
    
    args = parser.parse_args()

    
    db = Database()
    db.connect()
    
    if args.command == 'add_contacts':
        contacts_dict = contacts_dict_from_csv_file(args.contacts_csv_file)
        db.add_contacts(contacts_dict)
        db.mysql_connection.commit()
    elif args.command == 'read_calls':
        pprint.pprint(db.read_calls())
    elif args.command == 'read_texts':
        pprint.pprint(db.read_texts())
    elif args.command == "schedule_text":
        db.schedule_text(args.user_id, args.message, args.schedule_datetime)
        db.mysql_connection.commit()
    elif args.command == "schedule_call":
        db.schedule_call(args.contact_a_id, args.contact_b_id, args.schedule_datetime)
        db.mysql_connection.commit()

