#!/usr/bin/env python3
""" Twilio Text and Phone dispatcher.
This should be split out to a twilio service (potentially shared fate with the webservice)
driven via pubsub.
"""

import logging
import os
import sys

from cloud_handler import CloudLoggingHandler
from google.cloud import pubsub_v1
from google.cloud import spanner
from google.cloud.spanner_v1 import param_types
import argparse
import base64
import database
import datetime
import pdb
import time
import uuid

# TODO project_id = "Your Google Cloud Project ID"
# TODO topic_name = "Your Pub/Sub topic name"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, topic_name)


processor_uuid = base64.b64encode(uuid.uuid1().bytes)

SPANNER_INSTANCE_ID = "test-instance"
SPANNER_DATABASE_ID = "phone_schedule"
PROJECT = 'hazel-strand-270418' 
TOPIC = 'scheduler'

root_logger = None

def setup_logging(logger_name='cron_executor'):
    root_logger = logging.getLogger(logger_name)
    root_logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)
    cloud_handler = CloudLoggingHandler(on_gce=True, logname="task_runner")
    root_logger.addHandler(cloud_handler)



def process_single_call(instance_id, database_id):
    all_calls = database.read_calls(instance_id, database_id)
    claimed_call_uuid = None
    for call_uuid in all_calls.keys():
        if database.attempt_lock_call(
                instance_id, database_id, call_uuid, processor_uuid):
            claimed_call_uuid = call_uuid
            print("Worker dispatching %s" % claimed_text_uuid)
            break
    # Twilio to dial these numbers.

def process_single_text(instance_id, database_id):
    all_texts = database.read_texts(instance_id, database_id)
    claimed_text_uuid = None
    for text_uuid in all_texts.keys():
        if database.attempt_lock_text(
                instance_id, database_id, text_uuid, processor_uuid):
            claimed_text_uuid = text_uuid
            print("Worker dispatching %s" % claimed_text_uuid)
            break

def process_texts(instance_id, database_id):
    all_texts = database.read_texts(instance_id, database_id)



        
class DispatcherService():
    def __init__(self):
        pass

    def process_queue(self):
        
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
    subparsers.add_parser('process_single_call', help=process_single_call.__doc__)
    subparsers.add_parser('process_single_text', help=process_single_text.__doc__)
    args = parser.parse_args()
    

    if args.command == 'process_single_call':
        process_single_call(args.instance_id, args.database_id)
    if args.command == 'process_single_text':
        process_single_text(args.instance_id, args.database_id)

    if args.command == 'process_calls':
        while True:
            process_single_call(args.instance_id, args.database_id)
            sleep(60)
    if args.command == 'process_texts':
        while True:
            process_single_text(args.instance_id, args.database_id)
            sleep(60)
