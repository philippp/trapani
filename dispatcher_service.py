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
import crypto

SPANNER_INSTANCE_ID = "test-instance"
SPANNER_DATABASE_ID = "phone_schedule"
CYCLE_LOG_N = 10
SLEEP_PERIOD_SECONDS = 10
HTTP_REQUEST_PERIOD = 2  # 0.5 QPS
CYCLE = 0

TWILIO_WEB_DOMAIN = "35.223.137.150"
TWILIO_WEB_PORT = "8000"

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
        self.cryptmaster = crypto.Cryptmaster()

        server_address = ('0.0.0.0', 8000)
        self.httpd = http.server.HTTPServer(server_address, ProofOfLifeHandler)
        self.httpd.timeout = HTTP_REQUEST_PERIOD
        
    def dispatch_one(self, itemtype="text"):
        """
        Dispatch one message and return.
        """
        assert itemtype in ("text", "call")
        if itemtype == "text":
            db_item_table_name = "Texts"
            all_items = self.database.read_texts(exclude_processed = True)
        else:
            db_item_table_name = "Calls"
            all_items = self.database.read_calls(exclude_processed = True)

        claimed_item_uuid = None
        for item_uuid in all_items.keys():
            if claimed_item_uuid:
                break
            if self.database.attempt_lock_entity(
                    item_uuid,
                    db_item_table_name,
                    self.instance_uuid):
                claimed_item_uuid = item_uuid
                print("Worker dispatching %s" % claimed_item_uuid)
        if claimed_item_uuid:
            if itemtype == "text":
                if self._twilio_send_text(all_items[claimed_item_uuid]['PhoneNumber'],
                                          all_items[claimed_item_uuid]['Message']):
                    return True
            else:
                phone_numbers = [r.get("PhoneNumber") for r in all_items[claimed_item_uuid]['recipients']]
                if self._twilio_call(phone_numbers):
                    return True
        return False
                        
    def _twilio_send_text(self, target_number, message):
        if self.dry_run:
            print("Dry run: Would have sent \"%s\" to %s" % (message, target_number))
        else:
            r = self.client.messages.create(
                from_=self.client_phone_number,
                to=target_number,
                status_callback='https://postb.in/1583720040316-0948757505975',
                body=message)
            if r.error_code:
                print("Error: [%s] %s" % (error_code, error_message))
            print("Sent: %s" % r)

            
    def _twilio_call(self, target_number_list, call_template="alpha_20min"):
        encrypted_number = self.cryptmaster.encrypt_string(target_number_list[1]).decode()
        encrypted_number = encrypted_number.replace("=","")
        url = "http://%s:%d/dialpartner?ptoken=%s&template=%s" % (
            TWILIO_WEB_DOMAIN,
            int(TWILIO_WEB_PORT),
            encrypted_number,
            call_template)

        if self.dry_run:
            print("Dry run: Would have called %s with call template %s and url %s" %\
                  (target_number_list, call_template, url))
        else:
            r = self.client.calls.create(from_=self.client_phone_number,
                                         to=target_number_list[0],
                                         url=url)
                                     
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
            if self.dispatch_one(itemtype='text'):
                print("Dispatched a text!")
            if self.dispatch_one(itemtype='call'):
                print("Dispatched a call!")
            if CYCLE % CYCLE_LOG_N == 0:
                print("Cycle %d" % CYCLE)
        
if __name__ == '__main__':  # noqa: C901
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--project_id', help='Your Project ID.', default="hazel-strand-270418")
    
    subparsers = parser.add_subparsers(dest='command')
    p = subparsers.add_parser('dispatch_one_text', help=DispatcherService.dispatch_one.__doc__)
    p.add_argument(
        '--dry_run', help='Does not initiate calls or texts.', const = True, nargs="?", default=False)

    p = subparsers.add_parser('dispatch_one_call', help=DispatcherService.dispatch_one.__doc__)
    p.add_argument(
        '--dry_run', help='Does not initiate calls or texts.', const = True, nargs="?", default=False)

    subparsers.add_parser('continuous', help=DispatcherService.continuous_dispatch.__doc__)

    args = parser.parse_args()
    dispatch = DispatcherService(twilio_auth_token.twilio_account_sid,
                           twilio_auth_token.twilio_token,
                           twilio_auth_token.twilio_phone,
                           args.dry_run
    )
    if args.command == 'dispatch_one_text':
        dispatch.dispatch_one(itemtype="text")
    elif args.command == 'dispatch_one_call':
        dispatch.dispatch_one(itemtype="call")
    else:
        dispatch.continuous_dispatch()
