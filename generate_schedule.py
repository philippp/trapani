#!/usr/bin/env python3
"""
Generate a random schedule of fake names and numbers,
set two years in the future.
"""
import argparse
import random
import csv
from gcloud import database
import datetime
from dateutil.relativedelta import relativedelta

HEADERS = ["Name A","Number A","Name B","Number B","Date YYYY-MM-DD","Time (PST) HH:MM"]

def make_contacts():
    contacts = list()
    for name in women_names + men_names:
        contacts.append({'name':name, 'number':random.randrange(1000000000, 9999999999)})
    return contacts

def generate_schedule(db, schedule_file_path, engagement_count):
    """ Generate a fake schedule to test import.
    All dates are 2 years in the future to avoid calling test numbers.
    """
    tz_pst = datetime.timezone(-datetime.timedelta(hours=7))
    #datetime.datetime.now(tz = tz).strftime("%Y-%m-%d %H:%H")
    dt_now = datetime.datetime.now(tz = tz_pst)
    contacts = make_contacts()
    with open(schedule_file_path, 'w') as csvfile:
        schedule_writer = csv.writer(csvfile)
        schedule_writer.writerow(HEADERS)
        for i in range(engagement_count):
            contact_a = contacts[random.randrange(0, len(contacts)-1)]
            contact_b = contacts[random.randrange(0, len(contacts)-1)]
            random_t_offset = datetime.timedelta(hours=random.randrange(0,96), minutes=random.randrange(0,60))
            engagement_dt = dt_now + relativedelta(years=2) + random_t_offset
            row = [
                contact_a['name'],
                contact_a['number'],
                contact_b['name'],
                contact_b['number'],
                engagement_dt.strftime("%Y-%m-%d"),
                engagement_dt.strftime("%H:%M")]
            schedule_writer.writerow(row)

women_names = ["Addison","Alivia","Allaya","Amarie","Amaris","Annabeth","Annalynn","Araminta","Ardys","Ashland","Avery","Bedegrayne","Bernadette","Billie","Birdee","Bliss","Brice","Brittany","Bryony","Cameo","Carol","Chalee","Christy","Corky","Cotovatre","Courage","Daelen","Dana","Darnell","Dawn","Delsie","Denita","Devon","Devona","Diamond","Divinity","Duff","Dustin","Dusty","Ellen","Eppie","Evelyn","Everilda","Falynn","Fanny","Faren","Freedom","Gala","Galen","Gardenia"]
men_names = ["Adney","Aldo","Aleyn","Alford","Amherst","Angel","Anson","Archibald","Aries","Arwen","Astin","Atley","Atwell","Audie","Avery","Ayers","Baker","Balder","Ballentine","Bardalph","Barker","Barric","Bayard","Bishop","Blaan","Blackburn","Blade","Blaine","Blaze","Bramwell","Brant","Brawley","Breri","Briar","Brighton","Broderick","Bronson","Bryce","Burdette","Burle","Byrd","Byron","Cabal","Cage","Cahir","Cavalon","Cedar","Chatillon","Churchill","Clachas"]
if __name__ == '__main__': 
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--project_id', help='Your Project ID.', default="hazel-strand-270418")
    parser.add_argument(
        '--engagements', help='Number of engagements to generate.', default=100)
    parser.add_argument(
        '--schedule_file_path', help='CSV containing blindchat schedule', default='/tmp/trapani_schedule.csv')
    parser.add_argument(
        '--db_config', help='dev or prod database', default="dev")

    args = parser.parse_args()
    db = database.Database()
    db_config = database.db_info.get(args.db_config)
    db.connect(db_config)
    generate_schedule(db, args.schedule_file_path, args.engagements)
