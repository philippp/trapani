#!/usr/bin/env python3
from twilio.twiml.voice_response import VoiceResponse, Say
from flask import Flask, request, Response
from twilio import twiml
import crypto
import pdb

app = Flask(__name__)

@app.route('/', methods=['GET'])
def root():
    return Response(str("a=42"), mimetype='text/xml')


@app.route('/sms', methods=['POST'])
def sms():
    number = request.form['From']
    message_body = request.form['Body']
    resp = twiml.Response()
    resp.message('Hello {}, you said: {}'.format(number, message_body))
    return Response(str(response), mimetype='text/xml')

@app.route('/hello_world', methods=['POST','GET'])
def hello_world():
    response = VoiceResponse()
    response.say('It seems to be working! Whoopee!')
    return Response(str(response), mimetype='text/xml')

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
        response.say("Connecting, please wait.")
        response.dial(number)
    return Response(str(response), mimetype='text/xml')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
