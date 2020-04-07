#!/usr/bin/env python3
from twilio.twiml.voice_response import VoiceResponse, Say, Dial
from flask import Flask, request, Response, g
from twilio import twiml
import crypto
import pdb
import pprint
import config
from gcloud import database
import argparse
import json

app = Flask(__name__)

def request_has_connection():
    return hasattr(g, 'dbconn')

def get_request_connection():
    if not request_has_connection():
        g.dbconn = database.Database()
        g.dbconn.connect(database.db_info[DB_INSTANCE])
    return g.dbconn

@app.teardown_request
def close_db_connection(ex):
    if request_has_connection():
        conn = get_request_connection()
        conn.close()

@app.route('/', methods=['GET'])
def root():
    return Response(str("<html>v=time<br/>%s</html>" % WEB_DOMAIN), mimetype='text/xml')


@app.route('/sms', methods=['POST'])
def sms():
    number = request.form['From']
    message_body = request.form['Body']
    resp = twiml.Response()
    resp.message('Hello {}, you said: {}'.format(number, message_body))
    return Response(str(response), mimetype='text/xml')

@app.route('/reporting/text/<text_id>', methods=['POST','GET'])
def reporting_text(text_id=0):
    message_body = request.form.get('Body')
    pprint.pprint(message_body)
    # p request.form
    # ImmutableMultiDict([('SmsSid', 'SM6a114820eea742f68d11f870f4e5498e'), ('From', '+16122556554'), ('MessageStatus', 'delivered'), ('SmsStatus', 'delivered'), ('ApiVersion', '2010-04-01'), ('AccountSid', 'ACf872c3854b7750e5dfbc8b31a4cce297'), ('MessageSid', 'SM6a114820eea742f68d11f870f4e5498e'), ('To', '+14154665727')])
    db_connection = get_request_connection()
    db_connection.update_entity_status("texts", text_id, request.form.get('SmsStatus'),
                                       json.dumps(request.form))
    db_connection.close()
    return Response(str("OK"), mimetype='text/xml')

@app.route('/reporting/call/<call_id>', methods=['POST','GET'])
def reporting_call(call_id=0):
    message_body = request.form.get('Body')
    pprint.pprint(message_body)
    db_connection = get_request_connection()
    db_connection.update_entity_status("calls", text_id, request.form.get('SmsStatus'),
                                       json.dumps(request.form))
    db_connection.close()    
    return Response(str("OK"), mimetype='text/xml')

@app.route('/dialstatus', methods=['POST','GET'])
def dialstatus():
    dial_status = request.args['DialStatus']
    number = request.form['From']
    if dial_status != "answered":
        response = VoiceResponse()
        response.say("Apologies, but we couldn't reach your partner. Let us know and we will reschedule.")
    return Response(str("OK"), mimetype='text/xml')

@app.route('/dialpartner', methods=['POST', 'GET'])
def bridge():
    ptoken = request.args['ptoken']
    pprint.pprint(request.form)
    answeredBy = request.args.get('AnsweredBy') or request.form.get('AnsweredBy')
    print(answeredBy)
    b64_padded_ptoken = ptoken + "=" * (4 - len(ptoken) % 4)
    response = VoiceResponse()
    if answeredBy in ("human", "unknown"):
        response.play("%s/media/welcome_please_wait.mp3" % config.WEB_DOMAIN_PROD, action="/dialstatus")
        dial = Dial()
        dial.conference(ptoken,
                        waitUrl="%s/media/ttv_hold_music.mp3" % config.WEB_DOMAIN_PROD,
                        waitMethod="GET")
        response.append(dial)
    else:
        response.hangup()
    return Response(str(response), mimetype='text/xml')

global WEB_DOMAIN
global DB_INSTANCE
if __name__ == '__main__':

    WEB_DOMAIN = config.WEB_DOMAIN_DEV
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--database', help='dev or prod database', default="dev")
    args = parser.parse_args()
    DB_INSTANCE = args.database
    app.run(host='0.0.0.0', port=5000)
else:
    DB_INSTANCE = "prod"
    WEB_DOMAIN = config.WEB_DOMAIN_PROD
