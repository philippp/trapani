#!/usr/bin/env python3
from gcloud import database
from twilio.rest import Client
from keys import twilio_auth_token
from twilio.base import exceptions as twilio_exceptions
import json
import base64
import uuid
import argparse
import pdb
import time
import http.server
import time
import crypto
import scheduler

CYCLE_LOG_N = 10
SLEEP_PERIOD_SECONDS = 2
HTTP_REQUEST_PERIOD = 2  # 0.5 QPS
CYCLE = 0

TWILIO_WEB_DOMAIN = {
    'prod':"35.223.137.150",
    'dev':"135.180.93.160:5000"
}

WARN_MESSAGE = "Apologies for the interruption! Your BlindChat will end in %d minutes."
END_MESSAGE = "We hope you enjoyed your %d minute BlindChat - ending your call now."

ANNOUNCEMENT_MESSAGES = {
    1: {
        'message' : WARN_MESSAGE % scheduler.WARN_BEFORE_END_IN_MINUTES,
        'end_call' : False
    },
    2: {
        'message' : END_MESSAGE % scheduler.CALL_LENGTH_IN_MINUTES,
        'end_call' : True
    }
}

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
    
    def __init__(self, account_sid, auth_token, client_phone_number, dry_run=False, db_instance=False, twilio_instance='dev'):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.client = Client(account_sid, auth_token)
        self.client_phone_number = client_phone_number
        self.processor_id = processor_id = uuid.uuid4().int & (1<<64)-1
        self.dry_run = dry_run

        self.database = database.Database()
        self.database.connect(database.db_info[db_instance])
        self.cryptmaster = crypto.Cryptmaster()
        self.twilio_web_domain = TWILIO_WEB_DOMAIN[twilio_instance]
        server_address = ('0.0.0.0', 8000)
        self.httpd = http.server.HTTPServer(server_address, ProofOfLifeHandler)
        self.httpd.timeout = HTTP_REQUEST_PERIOD
        
    def dispatch_one(self, itemtype="text"):
        """
        Dispatch one action item and return.
        Multiple workers/threads must be able to safely invoke this
        concurrently.
        """
        assert itemtype in ("text", "call", "announcement")
        if itemtype == "text":
            db_item_table_name = "texts"
            all_items = self.database.read_texts(exclude_processed = True)
        elif itemtype == "call":
            db_item_table_name = "calls"
            all_items = self.database.read_calls(exclude_processed = True)
        else:
            db_item_table_name = "announcements"
            all_items = self.database.read_announcements(exclude_processed = True)
        claimed_item_id = None
        for item_id in all_items.keys():
            if claimed_item_id:
                break
            if self.database.attempt_lock_entity(
                    item_id,
                    db_item_table_name,
                    self.processor_id):
                self.database.mysql_connection.commit()
                claimed_item_id = item_id
                print("Worker dispatching %s" % claimed_item_id)
        if claimed_item_id:
            item = all_items[claimed_item_id]
            if itemtype == "text":
                if self._twilio_send_text(
                        item['phone_number'],
                        item['message'],
                        claimed_item_id):
                    return True
            elif itemtype == "call":
                phone_numbers = [item['contact_a_number'], item['contact_b_number']]
                call_sid_tuple = self._twilio_call(phone_numbers, claimed_item_id)
                if call_sid_tuple and len(call_sid_tuple) == 2:
                    scheduler.program_call_announcements(
                        self.database, call_sid_tuple[0], item['engagement_id'])
                    scheduler.program_call_announcements(
                        self.database, call_sid_tuple[1], item['engagement_id'])
                    return True
                else:
                    print("Failed to schedule announcements, call_sid_tuple was %s" % \
                          call_sid_tuple)
            else:
                # Announcement!
                self._twilio_announcement(item['call_sid'], item['announcement_id'])

        return False

    def _twilio_announcement(self, call_sid, announcement_id):
        # If we do not need to hang up after the announcement, this is an empty string.
        hangup_str = ""
        if ANNOUNCEMENT_MESSAGES[announcement_id]['end_call']:
            hangup_str = "<Hangup/>"
        twiml_response = "<Response><Say>%s</Say>%s</Response>" % (
            ANNOUNCEMENT_MESSAGES[announcement_id]['message'],
            hangup_str)
        try:
            print(twiml_response)
            r = self.client.calls(call_sid).update(twiml=twiml_response)
        except twilio_exceptions.TwilioRestException as e:
            r = None
            print(e)
        print("Survived the exception")
        return None
        
    def _twilio_send_text(self, target_number, message, text_id):
        if self.dry_run:
            print("Dry run: Would have sent \"%s\" to %s" % (message, target_number))
        else:
            callback_url = "http://%s/reporting/text/%d" % (
                self.twilio_web_domain,
                text_id)
            r = self.client.messages.create(
                from_=self.client_phone_number,
                to=target_number,
                status_callback=callback_url,
                body=message)
            if r.error_code:
                print("Error: [%s] %s" % (error_code, error_message))
            print("Sent: %s" % r)

            
    def _twilio_call(self, target_number_list, call_id, call_template="alpha_20min"):
        encrypted_number = self.cryptmaster.encrypt_string(target_number_list[1]).decode()
        encrypted_number = encrypted_number.replace("=","")
        callback_url = "http://%s/reporting/call/%d" % (
            self.twilio_web_domain,
            call_id)
        
        url = "http://%s/dialpartner?ptoken=%s&template=%s" % (
            self.twilio_web_domain,
            encrypted_number,
            call_template)

        if self.dry_run:
            print("Dry run: Would have called %s with call template %s and url %s" %\
                  (target_number_list, call_template, url))
            return ("fake_test_sid_1", "fake_test_sid_2")
        else:
            r = self.client.calls.create(from_=self.client_phone_number,
                                         to=target_number_list[0],
                                         status_callback=callback_url,
                                         machine_detection='Enable',
                                         url=url) 
            r2 = self.client.calls.create(from_=self.client_phone_number,
                                          to=target_number_list[1],
                                          status_callback=callback_url,
                                          machine_detection='Enable',
                                          url=url)
            # TODO: return sid tuple (it's in r)
            return (r.sid, r2.sid)
                                     
    def continuous_dispatch(self):
        """
        Dispatch messages while the job is alive.
        """
        global CYCLE
        while True:
            start_t = time.time()
            if self.dispatch_one(itemtype='text'):
                print("Dispatched a text!")
            if self.dispatch_one(itemtype='call'):
                print("Dispatched a call!")
            if CYCLE % CYCLE_LOG_N == 0:
                print("Cycle %d" % CYCLE)

            for i in range(int(SLEEP_PERIOD_SECONDS / HTTP_REQUEST_PERIOD)):
                self.httpd.handle_request()
            end_t = time.time()
            remaining_sleep = SLEEP_PERIOD_SECONDS - (end_t - start_t)
            if remaining_sleep > 0:
                time.sleep(remaining_sleep)
            CYCLE += 1
        
if __name__ == '__main__':  # noqa: C901
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--project_id', help='Your Project ID.', default="hazel-strand-270418")
    parser.add_argument(
        '--database', help='dev or prod database', default="dev")
    parser.add_argument(
        '--twilio', help='dev or prod twilio service', default="dev")
    
    subparsers = parser.add_subparsers(dest='command')
    p = subparsers.add_parser('dispatch_one_text', help=DispatcherService.dispatch_one.__doc__)
    p.add_argument(
        '--dry_run', help='Does not initiate calls or texts.', const = True, nargs="?", default=False)

    p = subparsers.add_parser('dispatch_one_call', help=DispatcherService.dispatch_one.__doc__)
    p.add_argument(
        '--dry_run', help='Does not initiate calls or texts.', const = True, nargs="?", default=False)

    p = subparsers.add_parser('dispatch_one_announcement', help=DispatcherService.dispatch_one.__doc__)
    p.add_argument(
        '--dry_run', help='Does not initiate calls or texts.', const = True, nargs="?", default=False)
    
    p = subparsers.add_parser('continuous', help=DispatcherService.continuous_dispatch.__doc__)
    p.add_argument(
        '--dry_run', help='Does not initiate calls or texts.', const = True, nargs="?", default=False)

    args = parser.parse_args()
    dispatch = DispatcherService(
        twilio_auth_token.twilio_account_sid,
        twilio_auth_token.twilio_token,
        twilio_auth_token.twilio_phone,
        dry_run = getattr(args, 'dry_run', False),
        db_instance = args.database,
        twilio_instance = args.twilio
    )
    if args.command == 'dispatch_one_text':
        dispatch.dispatch_one(itemtype="text")
    elif args.command == 'dispatch_one_call':
        dispatch.dispatch_one(itemtype="call")
    elif args.command == 'dispatch_one_announcement':
        dispatch.dispatch_one(itemtype="announcement")        
    else:
        dispatch.continuous_dispatch()
