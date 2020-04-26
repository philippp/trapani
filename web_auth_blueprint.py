import flask
import crypto
import web_auth_decorator

auth_blueprint = flask.Blueprint('auth_blueprint', __name__)
cryptmaster = crypto.Cryptmaster()
web_passphrase = open('keys/web_passphrase').read()

@auth_blueprint.route('/login', methods=['GET'])
def login():
    return flask.render_template('login.tmpl')

@auth_blueprint.route('/login', methods=['POST'])
def login_post():
    password = flask.request.form.get('password')
    if password == web_passphrase:
        response = flask.make_response(flask.redirect("/", code=302))
        response.set_cookie(
            web_auth_decorator.SESSION_COOKIE_NAME,
            cryptmaster.encrypt_string(web_auth_decorator.SESSION_EXPECTED_VALUE))
        return response
    else:
        return flask.redirect("/login?status=failed", code=302)

        # set cookie


    
    
