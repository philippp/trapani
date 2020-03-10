#!/usr/bin/env python3
from gcloud import database
from twilio.rest import Client
from google.cloud import spanner
from keys import twilio_auth_token
import json
import base64
import uuid
import argparse
import pdb
import time
import http.server
import time

SPANNER_INSTANCE_ID = "test-instance"
SPANNER_DATABASE_ID = "phone_schedule"
CYCLE_LOG_N = 10
SLEEP_PERIOD_SECONDS = 10
HTTP_REQUEST_PERIOD = 2  # 0.5 QPS
CYCLE = 0
#def run(server_class=HTTPServer, handler_class=BaseHTTPRequestHandler):

#This class will handles any incoming request from
#the browser 
class ProofOfLifeHandler(http.server.BaseHTTPRequestHandler):
    #Handler for the GET requests
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/html')
        self.end_headers()
        # Send the html message
        self.wfile.write(("OK. Cycle %d and going." % CYCLE).encode())
        return
    
class DispatcherService():
    
    def __init__(self, account_sid, auth_token, client_phone_number, dry_run=False):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.client = Client(account_sid, auth_token)
        self.client_phone_number = client_phone_number
        self.instance_uuid = base64.b64encode(uuid.uuid1().bytes)
        self.dry_run = dry_run
        self.database = database.Database(SPANNER_INSTANCE_ID, SPANNER_DATABASE_ID)
        self.database.connect()

        server_address = ('0.0.0.0', 8000)
        self.httpd = http.server.HTTPServer(server_address, ProofOfLifeHandler)
        self.httpd.timeout = HTTP_REQUEST_PERIOD
        
    def dispatch_one_text(self):
        """
        Dispatch one message and return.
        """
        all_texts = self.database.read_texts(exclude_processed = True)
        claimed_text_uuid = None
        for text_uuid in all_texts.keys():
            if claimed_text_uuid:
                break
            if self.database.attempt_lock_text(text_uuid, self.instance_uuid):
                claimed_text_uuid = text_uuid
                print("Worker dispatching %s" % claimed_text_uuid)
        if claimed_text_uuid:
            if self._send_text(all_texts[claimed_text_uuid]['PhoneNumber'],
                               all_texts[claimed_text_uuid]['Message']):
                return True
        return False
            
            
            
    def _send_text(self, target_number, message):
        if self.dry_run:
            print("Dry run: Would have sent \"%s\" to %s" % (message, target_number))
        r = self.client.messages.create(
            from_=self.client_phone_number,
            to=target_number,
            status_callback='https://postb.in/1583720040316-0948757505975',
            body=message)
        if r.error_code:
            print("Error: [%s] %s" % (error_code, error_message))
            return False
        print("Sent: %s" % r)

    def continuous_dispatch(self):
        """
        Dispatch messages while the job is alive.
        """
        global CYCLE
        while True:
            start_t = time.time()
            for i in range(int(SLEEP_PERIOD_SECONDS / HTTP_REQUEST_PERIOD)):
                self.httpd.handle_request()
            end_t = time.time()
            remaining_sleep = SLEEP_PERIOD_SECONDS - (end_t - start_t)
            if remaining_sleep > 0:
                time.sleep(remaining_sleep)
            CYCLE += 1
            if self.dispatch_one_text():
                print("Dispatched a text!")
            if CYCLE % CYCLE_LOG_N == 0:
                print("Cycle %d" % CYCLE)
        
if __name__ == '__main__':  # noqa: C901
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--project_id', help='Your Project ID.', default="hazel-strand-270418")

    parser.add_argument(
        '--dry_run', help='Does not initiate calls or texts.', default=False)
    
    subparsers = parser.add_subparsers(dest='command')
    subparsers.add_parser('dispatch_one_text', help=DispatcherService.dispatch_one_text.__doc__)
    subparsers.add_parser('continuous_dispatch', help=DispatcherService.continuous_dispatch.__doc__)

    args = parser.parse_args()
    dispatch = DispatcherService(twilio_auth_token.twilio_account_sid,
                           twilio_auth_token.twilio_token,
                           twilio_auth_token.twilio_phone,
                           args.dry_run
    )
        
    if args.command == 'dispatch_one_text':
        dispatch.dispatch_one_text(dry_ryn = args.dry_run)
    elif args.command == 'continuous_dispatch':
        dispatch.continuous_dispatch()
