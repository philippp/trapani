import flask
from functools import wraps
import crypto


SESSION_COOKIE_NAME = "BLINDCHAT_SID"
SESSION_EXPECTED_VALUE = "fancy"

cryptmaster = crypto.Cryptmaster()

def valid_credentials(sid_value):
    return sid_value and cryptmaster.decrypt_string(sid_value) == "fancy"

def authenticate(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not valid_credentials(flask.request.cookies.get(SESSION_COOKIE_NAME)):
            return flask.redirect('/login?status=unauthenticated', code=302)
        return f(*args, **kwargs)
    return wrapper
