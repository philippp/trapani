#!/usr/bin/env python3
from collections import defaultdict
from flask import request, Response, g, redirect
import flask
from gcloud import database
from twilio import twiml
from twilio.twiml.voice_response import VoiceResponse, Say, Dial
import mysql.connector.errors
import argparse
import config
import crypto
import dateutil
from dateutil.relativedelta import relativedelta
import json
import pdb
import pprint
import datetime
import pytz
import jinja2

app = flask.Flask(__name__)

def convert_utc_datetime_to_pst_str(dt):
    if not dt:
        return ""
    utc = pytz.timezone('UTC')
    aware_dt = utc.localize(dt)
    pst = pytz.timezone('US/Pacific')
    pacific_date = aware_dt.astimezone(pst)
    return pacific_date.strftime("%Y-%m-%d %H:%M:%S")

def convert_utc_datetime_to_relative_str(dt): #relativedelta_to_str(rd):
    rd = relativedelta(dt, datetime.datetime.utcnow())

    time_str = ""
    fragments = list()
    if rd.days != 0:
        fragments.append("%d days" % abs(rd.days))
    if rd.hours != 0:
        fragments.append("%d hours" % abs(rd.hours))
    if rd.days == 0 and rd.minutes != 0:
        fragments.append("%d minutes" % abs(rd.minutes))
    if len(fragments) == 2:
        time_str = " and ".join(fragments)
    elif len(fragments) == 3:
        time_str = "%s, %s, and %s" % fragments
    elif fragments:
        time_str = fragments[0]
    else:
        return ""
    if rd.days < 0 or rd.hours < 0 or rd.minutes < 0:
        return time_str + " ago"
    else:
        return "in " + time_str

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

@app.route('/engagements', methods=['GET'])
def engagements():
    db_connection = get_request_connection()
    calls = db_connection.read_calls()
    for call in calls.values():
        # Convert timestamps to PST
        call['time_scheduled_pst'] = convert_utc_datetime_to_pst_str(call['time_scheduled'])
        call['time_processed_pst'] = convert_utc_datetime_to_pst_str(call['time_dispatcher_processed'])
        call['time_scheduled_str'] = convert_utc_datetime_to_relative_str(call['time_scheduled'])
        rd = relativedelta(call['time_scheduled'], datetime.datetime.utcnow())
        call['relative_delta'] = rd
    return flask.render_template('engagements.tmpl',
                                 calls = sorted(calls.values(), key=lambda c: c['time_scheduled'])[::-1])

@app.route('/list_pairs', methods=['GET'])
def list_pairs():
    db_connection = get_request_connection()
    calls = db_connection.read_calls()

    calls_by_couple = defaultdict(list)
    f_couplekey = lambda c: "%s & %s" % tuple(sorted([c['contact_a_name'], c['contact_b_name']]))

    for call in calls.values():
        # Convert timestamps to PST
        call['time_scheduled_pst'] = convert_utc_datetime_to_pst_str(call['time_scheduled'])
        call['time_processed_pst'] = convert_utc_datetime_to_pst_str(call['time_dispatcher_processed'])
        call['time_scheduled_str'] = convert_utc_datetime_to_relative_str(call['time_scheduled'])
        rd = relativedelta(call['time_scheduled'], datetime.datetime.utcnow())
        call['relative_delta'] = rd
        calls_by_couple[f_couplekey(call)].append(call)
    return flask.render_template('engagements.tmpl', calls_by_couple = calls_by_couple)

@app.route('/contacts', methods=['GET'])
def contacts():
    db_connection = get_request_connection()
    contacts = db_connection.read_contacts()
    for contact in contacts:
        print(type(contact['latest_time_scheduled']))
        print(contact['latest_time_scheduled'])
        print("\n")
        contact['latest_time_scheduled_pst'] = convert_utc_datetime_to_relative_str(
            contact['latest_time_scheduled'])
    return flask.render_template('list_contacts.tmpl', contacts = contacts)

@app.route('/contact/<contact_id>', methods=['GET'])
def contact(contact_id):
    db_connection = get_request_connection()
    contact_list = db_connection.read_contacts()
    contact_list_minimal = list()
    profile_contact = None
    for c in contact_list:
        contact_list_minimal.append(dict(
            id = c['id'],
            name = c['name'],
            phone_number = c['phone_number']))
        if str(c['id']) == contact_id:
            profile_contact = c
    if not profile_contact:
        return Response(str("User ID not found"), mimetype='text/xml')
    calls = db_connection.read_calls(contact_id = contact_id)
    calls_by_couple = defaultdict(lambda: defaultdict(list))
    f_couplename = lambda c: "%s & %s" % tuple(sorted([c['contact_a_name'], c['contact_b_name']]))
    f_couplekey = lambda c: "%d_%d" % tuple(sorted([c['contact_a_id'], c['contact_b_id']]))
    for call in calls.values():
        # Convert timestamps to PST
        call['time_scheduled_pst'] = convert_utc_datetime_to_pst_str(call['time_scheduled'])
        call['time_processed_pst'] = convert_utc_datetime_to_pst_str(call['time_dispatcher_processed'])
        call['time_scheduled_str'] = convert_utc_datetime_to_relative_str(call['time_scheduled'])
        rd = relativedelta(call['time_scheduled'], datetime.datetime.utcnow())
        call['relative_delta'] = rd
        couple_key = f_couplekey(call)
        calls_by_couple[couple_key]['calls'].append(call)
        calls_by_couple[couple_key]['couple_name'] = f_couplename(call)
        calls_by_couple[couple_key]['contact_a_id'] = call['contact_a_id']
        calls_by_couple[couple_key]['contact_b_id'] = call['contact_b_id']
        
    return flask.render_template('contact.tmpl',
                                 contact = profile_contact,
                                 calls_by_couple = calls_by_couple,
                                 contact_list_minimal = contact_list_minimal)

@app.route('/contact_edit', methods=['GET'])
def contact_edit_form():
    contact_id = request.args.get('contact_id')
    if contact_id:
        db_connection = get_request_connection()
        contact_list = db_connection.read_contacts(contact_id = contact_id)
        if not contact_list:
            return Response(str("User ID not found"), mimetype='text/xml')
        contact = contact_list[0]
    else:
        contact = defaultdict(str)
    #number = request.form['From']
    return flask.render_template('contact_edit.tmpl', contact = contact)

@app.route('/contact_edit', methods=['POST'])
def contact_edit_process():
    contact_id = request.form.get('contact_id')
    db_connection = get_request_connection()
    if contact_id:
        db_connection.edit_contact(contact_id, request.form.get('name'), request.form.get('phone_number'))
    else:
        contact = dict(
            name = request.form.get('name'),
            phone_number = request.form.get('phone_number')
        )
        try:
            db_connection.add_contacts([contact])
        except mysql.connector.errors.IntegrityError as e:
            return Response("<html><pre>"+str(e.msg)+"</pre></html>", mimetype='text/xml')            
    return redirect("/contacts", code=302)

@app.route('/engagement_create', methods=['GET'])
def engagement_create():
    contact_a_id = request.args.get('contact_a_id')
    contact_b_id = request.args.get('contact_b_id')
    db_connection = get_request_connection()    
    contact_list = db_connection.read_contacts()
    contact_list_minimal = list()
    contact_a = defaultdict(str)
    contact_b = defaultdict(str)
    for c in contact_list:
        if str(c['id']) == contact_a_id:
            contact_a = c
        elif str(c['id']) == contact_b_id:
            contact_b = c

    return flask.render_template('engagement_create.tmpl',
                                 contact_a = contact_a,
                                 contact_b = contact_b)

@app.route('/engagement_create', methods=['POST'])
def engagement_create_post():
    pprint.pprint(request.form)
    return flask.render_template('engagement_create.tmpl')

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
