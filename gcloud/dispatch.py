#!/usr/bin/env python3
""" Twilio Text and Phone dispatcher.
This should be split out to a twilio service (potentially shared fate with the webservice)
driven via pubsub.
"""
import pdb
import argparse
import base64
import datetime
import uuid
from google.cloud import spanner
from google.cloud.spanner_v1 import param_types
from cloud_handler import CloudLoggingHandler
import database
processor_uuid = base64.b64encode(uuid.uuid1().bytes)

def process_single_call(instance_id, database_id):
    all_calls = database.read_calls(instance_id, database_id)
    claimed_call_uuid = None
    for call_uuid in all_calls.keys():
        if database.attempt_lock_call(
                instance_id, database_id, call_uuid, processor_uuid):
            claimed_call_uuid = call_uuid
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
    
