#!/usr/bin/env python3
from twilio.twiml.voice_response import VoiceResponse, Say
from flask import Flask, request, Response
from twilio import twiml
import crypto
import pdb

app = Flask(__name__)

@app.route('/', methods=['GET'])
def root():
    return Response(str("<html>a=42</html>"), mimetype='text/xml')


@app.route('/sms', methods=['POST'])
def sms():
    number = request.form['From']
    message_body = request.form['Body']
    resp = twiml.Response()
    resp.message('Hello {}, you said: {}'.format(number, message_body))
    return Response(str(response), mimetype='text/xml')

@app.route('/reporting/text/<text_id>', methods=['POST','GET'])
def reporting_text(text_id):
    number = request.form['From']
    message_body = request.form['Body']
    return Response(str("OK"), mimetype='text/xml')

@app.route('/reporting/call/<call_id>', methods=['POST','GET'])
def reporting_call(text_id):
    number = request.form['From']
    message_body = request.form['Body']
    return Response(str("OK"), mimetype='text/xml')

@app.route('/dialpartner', methods=['POST', 'GET'])
def bridge():
    cryptmaster = crypto.Cryptmaster()
    ptoken = request.args['ptoken']
    b64_padded_ptoken = ptoken + "=" * (4 - len(ptoken) % 4)
    number = cryptmaster.decrypt_string(b64_padded_ptoken.encode())
    if not (number[0] == '+' and len(number) == 12):
        response = VoiceResponse()
        response.say("Apologies, but please tell the team you ran into error #1")
    else:
        response = VoiceResponse()
        response.play("http://35.223.137.150/media/welcome_please_wait.mp3")
        response.dial(number)
    return Response(str(response), mimetype='text/xml')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
