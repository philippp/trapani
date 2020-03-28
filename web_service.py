#!/usr/bin/env python3
from twilio.twiml.voice_response import VoiceResponse, Say, Dial
from flask import Flask, request, Response
from twilio import twiml
import crypto
import pdb
import pprint

ROOT_DOMAIN_DEV = "http://135.180.93.160:5000"
ROOT_DOMAIN_PROD = "http://35.223.137.150"

app = Flask(__name__)

@app.route('/', methods=['GET'])
def root():
    return Response(str("<html>v=time<br/>%s</html>" % ROOT_DOMAIN), mimetype='text/xml')


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
    return Response(str("OK"), mimetype='text/xml')

@app.route('/reporting/call/<call_id>', methods=['POST','GET'])
def reporting_call(call_id=0):
    message_body = request.form.get('Body')
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
    if answeredBy == "human":
        response.play("%s/media/welcome_please_wait.mp3" % ROOT_DOMAIN_PROD, action="/dialstatus")
        dial = Dial()
        dial.conference(ptoken,
                        waitUrl="%s/media/ttv_hold_music.mp3" % ROOT_DOMAIN_PROD,
                        waitMethod="GET")
        response.append(dial)
    else:
        response.hangup()
    return Response(str(response), mimetype='text/xml')


if __name__ == '__main__':
    global ROOT_DOMAIN
    ROOT_DOMAIN = ROOT_DOMAIN_DEV
    app.run(host='0.0.0.0', port=5000)
else:
    global ROOT_DOMAIN
    ROOT_DOMAIN = ROOT_DOMAIN_PROD
