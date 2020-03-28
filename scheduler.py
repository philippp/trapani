#!/usr/bin/env python3
import dateutil
import csv
from gcloud import database
import argparse
import re
import datetime
import pprint
import pdb
TEXT_BEFORE_CALL_IN_MINUTES = 10

MESSAGE_TEMPLATES = {
    1: """Your BlindChat with %s is coming up in %d minutes. Get cozy in a quiet spot! Consider breaking the ice by sharing your favorite travel memory.""",
    2: """Your 2nd BlindChat with %s is starting in %d minutes. Grab a quiet spot and think about this icebreaker: For what in your life do you feel most grateful?""",
    3: """Your 3rd BlindChat with %s is coming up in %d minutes. Grab a quiet spot and ponder this icebreaker: What's your biggest fear?""",
    4: """Wow, seems like you and %s are really hitting it off! Your next BlindChat is in %d minutes. Reflect on your last conversation, and enjoy!"""    
    
}

class Engagement:
    def __init__(self, schedule_row, contact_a, contact_b):
        self.contact_a = contact_a
        self.contact_b = contact_b
        self.time_call_scheduled = schedule_row[4]+"T"+schedule_row[5]
        
def format_phone_number(input_number):
    raw_number = "".join(re.findall(r'\d', input_number))
    if len(raw_number) == 10:
        raw_number = "1"+raw_number
    return "+"+raw_number


def program_schedule(db, schedule_file_path):
    with open(schedule_file_path) as schedule_file:
        schedule_reader = csv.reader(schedule_file)
        row_number = 0
        engagement_schedule = list()
        for row in schedule_reader:
            row_number += 1
            if row_number == 1:
                print(row)
                assert (
                    row[0] == 'Name A' and
                    row[1] == 'Number A' and
                    row[2] == 'Name B' and
                    row[3] == 'Number B' and
                    row[4] == 'Date YYYY-MM-DD' and
                    row[5] == 'Time (PST) HH:MM')
                continue
            assert ((row[4][4] == row[4][7] == '-') and len(row[4]) == 10)
            assert ((row[5][2] == ':') and len(row[5]) == 5)
            number_a = format_phone_number(row[1])
            number_b = format_phone_number(row[3])
            row_formatted = list(row)
            row_formatted[1] = number_a
            row_formatted[3] = number_b
            engagement_schedule.append(row_formatted)
        contact_map = get_or_create_contact_map(db, engagement_schedule)
        
        for schedule_row in engagement_schedule:
            engagement = Engagement(schedule_row,
                                    contact_map[schedule_row[1]],
                                    contact_map[schedule_row[3]])
            program_engagement(db, engagement, schedule_file_path)
        # pass

def get_or_create_contact_map(db, engagement_schedule):
    engagement_numbers = [[r[1],r[3]] for r in engagement_schedule]
    engagement_numbers = set([item for sublist in engagement_numbers for item in sublist])
    contact_map = dict()
    for contact in db.read_contacts_by_number(list(engagement_numbers)):
        contact_map[contact['phone_number']] = contact
    missing_numbers = engagement_numbers - set(contact_map.keys())
    if missing_numbers:
        contacts_to_add = list()
        numbers_to_add = set() # Helps us ensure we don't add the same contact twice!
        for r in engagement_schedule:
            print(r)
            if (r[1] not in contact_map.keys()) and r[1] not in numbers_to_add:
                numbers_to_add.add(r[1])
                contacts_to_add.append({
                    'name': r[0],
                    'phone_number':r[1]})

            if (r[3] not in contact_map.keys()) and r[3] not in numbers_to_add:
                numbers_to_add.add(r[3])                
                contacts_to_add.append({
                    'name': r[2],
                    'phone_number':r[3]})
        db.add_contacts(contacts_to_add)
        for contact in db.read_contacts_by_number(list(engagement_numbers)):
            contact_map[contact['phone_number']] = contact       
    return contact_map

def program_engagement(db, engagement, schedule_file_path):
    # Add engagement to DB
    # Avoid duplicate engagements and recognize follow-on engagements
    # by checking existing calls between the two.

    existing_calls = db.read_calls(caller_numbers = [engagement.contact_a['phone_number'],
                                                     engagement.contact_b['phone_number']])

    dt = dateutil.parser.parse(engagement.time_call_scheduled+"-07:00")
    new_engagement_time_scheduled = dt.astimezone(
        tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    print("Evaluating engagement to be scheduled for %s" % new_engagement_time_scheduled)
    for existing_call in existing_calls.values():
        if existing_call['time_scheduled'].strftime("%Y-%m-%d %H:%M:%S") == new_engagement_time_scheduled:
            print("Would have been a dupe, skipping.")
            return
    engagement_number = len(existing_calls) + 1
            
    engagement_id = db.register_engagement(schedule_file_path, engagement.time_call_scheduled, engagement_number)
    program_texts(db, engagement, engagement_id, engagement_number)
    program_call(db, engagement, engagement_id)

def program_texts(db, engagement, engagement_id, engagement_number):
    dt_call = dateutil.parser.parse(engagement.time_call_scheduled+"-07:00")
    dt_text = dt_call - datetime.timedelta(minutes=TEXT_BEFORE_CALL_IN_MINUTES)
    datestring_text = dt_text.strftime("%Y-%m-%dT%H:%M:%S")
    print("Scheduling texts at %s (call will be at %s)" % (datestring_text, engagement.time_call_scheduled))
    engagement_number = min(engagement_number, max(MESSAGE_TEMPLATES.keys()))
    db.schedule_text(engagement.contact_a['id'],
                     MESSAGE_TEMPLATES[engagement_number] % (engagement.contact_b['name'],
                                         TEXT_BEFORE_CALL_IN_MINUTES),
                     datestring_text)
    db.schedule_text(engagement.contact_b['id'],
                     MESSAGE_TEMPLATES[engagement_number] % (engagement.contact_a['name'],
                                         TEXT_BEFORE_CALL_IN_MINUTES),
                     datestring_text,
                     engagement_id = engagement_id)

def program_call(db, engagement, engagement_id):
    db.schedule_call(engagement.contact_a['id'],
                     engagement.contact_b['id'],
                     engagement.time_call_scheduled,
                     engagement_id = engagement_id)
    
if __name__ == '__main__': 
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--project_id', help='Your Project ID.', default="hazel-strand-270418")
    parser.add_argument(
        '--db_config', help='dev or prod database', default="dev")
    parser.add_argument(
        '--schedule_file_path', help='CSV containing trapani schedule')

    args = parser.parse_args()
    
    db = database.Database()
    db_config = database.db_info.get(args.db_config)
    db.connect(db_config)
    program_schedule(db, args.schedule_file_path)
