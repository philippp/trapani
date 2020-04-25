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
import dateutil.parser
import mysql.connector
import csv

db_info = dict(
    dev = dict(
        host='localhost',
        user='blindchat_dev',
        passwd='u73hYgt!GHkn7!8E39',
        database='blindchat_dev',
        port=3307
    ),
    prod = dict(
        host='localhost',
        user='blindchat_prod',
        passwd='Y5fR2)3_3bnGbKME21',
        database='blindchat_prod',
        port=3307
    ),
)

def execute(cursor, query, values=None):
    return cursor.execute(query, values)
    
class Database:

    def __init__(self):
        self.mysql_connection = None

    def connect(self, config):
        self.config = config
        self.reconnect()


    def close(self):
        try:
            if self.mysql_connection:
                self.mysql_connection.close()
                del self.mysql_connection
        except:
            pass
            
    def reconnect(self):
        try:
            if self.mysql_connection:
                self.mysql_connection.close()
        except:
            pass
        self.mysql_connection = mysql.connector.connect(**self.config)

    def read_contacts(self, numbers = None, contact_id = None):
        where_clause = ""
        sql_var = None
        if numbers:
            sql_var = tuple(numbers)
            where_clause = "WHERE phone_number IN (%s)" % ",".join(['%s'] * len(numbers))
        elif contact_id:
            sql_var = (contact_id,)
            where_clause = "WHERE contacts.id = %s "
            
        sql_query = """
SELECT
  contacts.id,
  name,
  phone_number,
  contacts.time_created,
  GREATEST(MAX(COALESCE(calls_a.time_scheduled, 0)), MAX(COALESCE(calls_b.time_scheduled, 0))) as latest_time_scheduled,
  COUNT(DISTINCT calls_a.id) + COUNT(DISTINCT calls_b.id) as total_calls,
  COUNT(DISTINCT calls_a.contact_b_id) + COUNT(DISTINCT calls_b.contact_a_id) as distinct_partners
FROM
  contacts
LEFT JOIN
  calls as calls_a
ON contacts.id = calls_a.contact_a_id
LEFT JOIN
  calls as calls_b
ON contacts.id = calls_b.contact_b_id
""" + where_clause + """
GROUP BY 1,2,3,4
ORDER BY 5 DESC
"""

        cursor = self.mysql_connection.cursor()
        if sql_var is not None:
            cursor.execute(sql_query, sql_var)
        else:
            cursor.execute(sql_query)
        records = cursor.fetchall()
        self.mysql_connection.commit()
        return_list = list()
        for r in records:
            r_modified = list(r)
            if r[4] and r[4] != '0':
                r_modified[4] = dateutil.parser.parse(r[4])
            else:
                r_modified[4] = None
            return_list.append(
                dict(zip(
                    ('id', 'name', 'phone_number', 'time_created', 'latest_time_scheduled',
                     'total_calls', 'distinct_partners'),r_modified)))
        return return_list
    
    def read_texts(self, cutoff_time=None, exclude_processed=False):
        sql_query = """
SELECT 
  texts.id as text_id, 
  contact_id, 
  contacts.name,
  contacts.phone_number,
  texts.message
FROM texts
LEFT JOIN contacts ON contact_id = contacts.id
"""
        sql_query_params = []
        if cutoff_time or exclude_processed:
            sql_query += " WHERE "
            clauses = []
            if cutoff_time:
                clauses.append(" time_scheduled <= %s ")
                sql_query_params.append(cutoff_time)
            if exclude_processed:
                clauses.append(" processor_id IS NULL ")
            sql_query += ("AND".join(clauses))
                
        cursor = self.mysql_connection.cursor()
        
        cursor.execute(sql_query, sql_query_params)
        records = cursor.fetchall()
        self.mysql_connection.commit()
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

    def read_engagements(self, cutoff_time=None):
        sql_query = """
SELECT 
  id, 
  time_scheduled, 
  time_created,
  engagement_number,
  schedule_file_path
FROM engagements
"""
        sql_query_params = []
        if cutoff_time:
            sql_query += " WHERE time_scheduled <= %s "
                
        cursor = self.mysql_connection.cursor()
        
        cursor.execute(sql_query, sql_query_params)
        records = cursor.fetchall()
        self.mysql_connection.commit()
        engagements = dict()
        for row in records:
            engagements[row[0]] = {
                'id' : row[0],
                'time_scheduled' : row[1],
                'time_created' : row[2],
                'engagement_number' : row[3],
                'schedule_file_path' : row[4]
            }
        return engagements

    
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
        result = cursor.rowcount
        self.mysql_connection.commit()
        return result

    def read_calls(self, cutoff_time=None, exclude_processed=False,
                   caller_numbers=None, contact_id = None):
        """
        List all calls in the system.
        cutoff_time: If specified, only read calls scheduled before this time.
        exclude_processed: If specified, only read unprocessed calls.
        caller_numbers (tuple): If specified, only read calls between these numbers.
        """
        pending_calls = dict()
        sql_query_params = []
        sql_query = """
SELECT 
  calls.id, 
  contact_a_id, 
  contact_b_id, 
  contacts_a.name as name_a,
  contacts_b.name as name_b,
  contacts_a.phone_number as number_a,
  contacts_b.phone_number as number_b,
  calls.time_scheduled,
  calls.time_dispatcher_processed,
  calls.engagement_id
FROM calls 
LEFT JOIN contacts as contacts_a 
ON calls.contact_a_id = contacts_a.id
LEFT JOIN contacts as contacts_b
ON calls.contact_b_id = contacts_b.id
"""
        if cutoff_time or exclude_processed or caller_numbers or contact_id:
            sql_query += " WHERE "
            clauses = []
            if exclude_processed:
                clauses.append(" processor_id IS NULL ")
            if caller_numbers and len(caller_numbers) == 2:
                clauses.append(""" (
                (contacts_a.phone_number = %s AND contacts_b.phone_number = %s) OR
                (contacts_b.phone_number = %s AND contacts_a.phone_number = %s))
                """)
                for number in list(caller_numbers) * 2:
                    sql_query_params.append(number)
            if contact_id:
                clauses.append(" (contact_a_id = %s OR contact_b_id = %s) ")
                sql_query_params.append(contact_id)
                sql_query_params.append(contact_id)                
            if cutoff_time:
                clauses.append(" time_scheduled <= %s")
                sql_query_params.append(cutoff_time)
            sql_query += " AND ".join(clauses)
            
        cursor = self.mysql_connection.cursor()
        cursor.execute(sql_query, tuple(sql_query_params))
        records = cursor.fetchall()
        self.mysql_connection.commit()
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
                'time_scheduled' : row[7],
                'time_dispatcher_processed' : row[8],
                'engagement_id' : row[9]
            }
        return pending_calls

    def edit_contact(self, contact_id, contact_name, contact_number):
        cursor = self.mysql_connection.cursor()
        insert_string = "UPDATE contacts SET name = %s, phone_number = %s WHERE id = %s"
        result = cursor.execute(
            insert_string,
            [contact_name, contact_number, contact_id])
        self.mysql_connection.commit()
        
    
    def add_contacts(self, contacts):
        """Adds contacts.
        Format is {'name':contact_name, 'phone_number':contact_number}
        """
        cursor = self.mysql_connection.cursor()
        insert_string = "INSERT INTO contacts (name, phone_number) " \
            "VALUES (%s,%s)"
        result = cursor.executemany(
            insert_string,
            [(c['name'], c['phone_number']) for c in contacts])
        self.mysql_connection.commit()
        
    def schedule_text(self, contact_id, message, time_scheduled, engagement_id=0):
        """Schedules a text message.
        TODO: Validate and reformat datetime and phone #"""
        # TODO - handle DST
        dt = dateutil.parser.parse(time_scheduled+"-07:00")
        time_scheduled = dt.astimezone(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.mysql_connection.cursor()
        insert_string = "INSERT INTO texts (contact_id, message, time_scheduled, engagement_id) " \
            "VALUES (%s,%s, %s, %s)"
        
        cursor.execute(insert_string, (contact_id, message, time_scheduled, engagement_id))
        self.mysql_connection.commit()
        print("Added scheduled text #%d" % cursor.lastrowid)

    def update_entity_status(self, entity_table_name, entity_id,
                             status, status_detail):
        # DO NOT REMOVE.
        # Using string substitition of this variable in SQL below.
        entity_id_fieldname = entity_table_name[:-1] + "_id"
        sql_query = ("UPDATE " + entity_table_name + " SET status = %s, "
                     "status_detail = %s"
               "WHERE id = %s")
        cursor = self.mysql_connection.cursor()
        cursor.execute(sql_query, (status, status_detail, entity_id))
        result = cursor.rowcount
        self.mysql_connection.commit()
        return result

    def schedule_call(self, contact_a_id, contact_b_id, time_scheduled, engagement_id=0):
        # TODO - handle DST
        dt = dateutil.parser.parse(time_scheduled+"-07:00")
        time_scheduled = dt.astimezone(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
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
        self.mysql_connection.commit()
        print("Added scheduled call #%d" % cursor.lastrowid)        
        
    def register_engagement(self, schedule_file_path, time_scheduled, engagement_number=1):
        insert_string = "INSERT INTO engagements (schedule_file_path, time_scheduled, engagement_number) VALUES (%s, %s, %s)"
        values = [schedule_file_path, time_scheduled, engagement_number]
        cursor = self.mysql_connection.cursor()
        cursor.execute(insert_string, values)
        self.mysql_connection.commit()
        return cursor.lastrowid
        
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
    parser.add_argument('--db_config', default="dev", help="dev or prod")

    subparsers = parser.add_subparsers(dest='command')
    add_contact_parser = subparsers.add_parser('add_contacts', help=Database.add_contacts.__doc__)
    add_contact_parser.add_argument('--contacts_csv_file', help="CSV of name, number columns")

    schedule_text_parser = subparsers.add_parser('schedule_text', help=Database.schedule_text.__doc__)
    schedule_text_parser.add_argument('--message', help="Text message to send, 160 chars max.")
    schedule_text_parser.add_argument('--user_id', help="User to schedule text for")
    schedule_text_parser.add_argument('--schedule_datetime',
                                      help="\"YYYY-MM-DDTHH:MM:SS\" In pacific time zone",
                                      default="2020-01-01T00:00:00")

    schedule_call_parser = subparsers.add_parser('schedule_call', help=Database.schedule_call.__doc__)
    schedule_call_parser.add_argument('--contact_a_id')
    schedule_call_parser.add_argument('--contact_b_id')
    schedule_call_parser.add_argument('--schedule_datetime',
                                      help="\"YYYY-MM-DDTHH:MM:SS\" In pacific time zone",
                                      default="2020-01-01T00:00:00")
    
    subparsers.add_parser('read_calls', help=Database.read_calls.__doc__)
    subparsers.add_parser('read_texts', help=Database.read_texts.__doc__)    
    
    args = parser.parse_args()

    
    db = Database()
    db_config = db_info.get(args.db_config)
    db.connect(db_config)
    
    if args.command == 'add_contacts':
        contacts_dict = contacts_dict_from_csv_file(args.contacts_csv_file)
        db.add_contacts(contacts_dict)
    elif args.command == 'read_calls':
        pprint.pprint(db.read_calls())
    elif args.command == 'read_texts':
        pprint.pprint(db.read_texts())
    elif args.command == "schedule_text":
        db.schedule_text(args.user_id, args.message, args.schedule_datetime)
    elif args.command == "schedule_call":
        db.schedule_call(args.contact_a_id, args.contact_b_id, args.schedule_datetime)


