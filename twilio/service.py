from twilio.twiml.voice_response import VoiceResponse, Say
from flask import Flask, request
from twilio import twiml


app = Flask(__name__)


@app.route('/sms', methods=['POST'])
def sms():
    number = request.form['From']
    message_body = request.form['Body']
    resp = twiml.Response()
    resp.message('Hello {}, you said: {}'.format(number, message_body))
    return str(resp)

@app.route('/hello_world', methods=['POST','GET'])
def hello_world():
    response = VoiceResponse()
    response.say('It seems to be working! Whoopee!')
    return str(response)

@app.route('/bridge', methods=['POST', 'GET'])
def bridge():
    response = VoiceResponse()
    response.say("Connecting, please wait.")
    response.dial("+14152904810")
    return str(response)


if __name__ == '__main__':
    app.run(host='0.0.0.0')
