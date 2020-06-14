import datetime
import pytz
import scheduler
import dateutil
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import mysql.connector.errors
import pprint
from flask import Flask, request, Response, redirect, g, current_app, Blueprint
import jinja2
import pdb
import flask
from web import auth_decorator

admin_blueprint = Blueprint('admin_blueprint', __name__)

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
    if rd.months != 0:
        fragments.append("%d months" % abs(rd.months))
    if rd.days != 0:
        fragments.append("%d days" % abs(rd.days))
    if rd.hours != 0:
        fragments.append("%d hours" % abs(rd.hours))
    if rd.days == 0 and rd.minutes != 0:
        fragments.append("%d minutes" % abs(rd.minutes))
    if len(fragments) == 2:
        time_str = " and ".join(fragments)
    elif len(fragments) == 3:
        pdb.set_trace()
        time_str = "%s, %s, and %s" % tuple(fragments)
    elif len(fragments) == 4:
        time_str = "%s, %s, %s, and %s" % tuple(fragments)
    elif fragments:
        time_str = fragments[0]
    else:
        return ""
    if rd.days < 0 or rd.hours < 0 or rd.minutes < 0:
        return time_str + " ago"
    else:
        return "in " + time_str

@admin_blueprint.route('/', methods=['GET'])
@auth_decorator.authenticate
def root():
    return flask.render_template('frontpage.tmpl')    
    
@admin_blueprint.route('/engagements', methods=['GET'])
@auth_decorator.authenticate
def engagements():
    db_connection = current_app.config['db_connection']
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

@admin_blueprint.route('/list_pairs', methods=['GET'])
@auth_decorator.authenticate
def list_pairs():
    db_connection = current_app.config['db_connection']
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

@admin_blueprint.route('/contacts', methods=['GET'])
@auth_decorator.authenticate
def contacts():
    db_connection = current_app.config['db_connection']
    contacts = db_connection.read_contacts()
    for contact in contacts:
        print(type(contact['latest_time_scheduled']))
        print(contact['latest_time_scheduled'])
        print("\n")
        contact['latest_time_scheduled_pst'] = convert_utc_datetime_to_relative_str(
            contact['latest_time_scheduled'])
    return flask.render_template('list_contacts.tmpl', contacts = contacts)

@admin_blueprint.route('/contact/<contact_id>', methods=['GET'])
@auth_decorator.authenticate
def contact(contact_id):
    db_connection = current_app.config['db_connection']
    contact_list = db_connection.read_contacts()
    profile_contact = None
    contact_list_minimal = list()
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
    profile_contact['latest_time_scheduled_pst'] = convert_utc_datetime_to_relative_str(
            profile_contact['latest_time_scheduled'])
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

@admin_blueprint.route('/contact_edit', methods=['GET'])
@auth_decorator.authenticate
def contact_edit_form():
    contact_id = request.args.get('contact_id')
    if contact_id:
        db_connection = current_app.config['db_connection']
        contact_list = db_connection.read_contacts(contact_id = contact_id)
        if not contact_list:
            return Response(str("User ID not found"), mimetype='text/xml')
        contact = contact_list[0]
    else:
        contact = defaultdict(str)
    #number = request.form['From']
    return flask.render_template('contact_edit.tmpl', contact = contact)

@admin_blueprint.route('/contact_edit', methods=['POST'])
@auth_decorator.authenticate
def contact_edit_process():
    contact_id = request.form.get('contact_id')
    db_connection = current_app.config['db_connection']
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

@admin_blueprint.route('/engagement_create', methods=['GET'])
@auth_decorator.authenticate
def engagement_create():
    contact_a_id = request.args.get('contact_a_id')
    contact_b_id = request.args.get('contact_b_id')
    db_connection = current_app.config['db_connection']    
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

@admin_blueprint.route('/engagement_create', methods=['POST'])
@auth_decorator.authenticate
def engagement_create_post():
    pprint.pprint(request.form)
    db = current_app.config['db_connection']
    contacts = db.read_contacts(numbers=[request.form['number_a'], request.form['number_b']])
    assert len(contacts) == 2
    time_call_scheduled_pst = request.form['date_str']+"T"+request.form['time_str']
    engagement = scheduler.Engagement(time_call_scheduled_pst, contacts[0], contacts[1])
    scheduler.program_engagement(db, engagement, 'web_service')
    return redirect("/contacts", code=302)
