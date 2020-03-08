# Download the helper library from https://www.twilio.com/docs/python/install
from twilio.rest import Client
import auth_token

# Your Account Sid and Auth Token from twilio.com/console
# DANGER! This is insecure. See http://twil.io/secure
client = Client(auth_token.twilio_account_sid, auth_token.twilio_token)

call = client.calls.create(
                        url='http://135.180.75.200:5000/bridge',
                        to='+14154665727',
                        from_='+16122556554'
                    )

print(call.sid)

