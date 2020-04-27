#!/usr/bin/env python3
from flask import Response, g, current_app
import flask
from gcloud import database
import argparse
import config
import pdb

from web.twilio_blueprint import twilio_blueprint
from web.admin_blueprint import admin_blueprint
from web.auth_blueprint import auth_blueprint

app = flask.Flask(__name__, template_folder='web/templates')

with app.app_context():
    app.register_blueprint(admin_blueprint)
    app.register_blueprint(twilio_blueprint)
    app.register_blueprint(auth_blueprint)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--database', help='dev or prod database', default="dev")
    args = parser.parse_args()
    with app.app_context():
        app.config['db_connection'] = database.Database()
        app.config['db_connection'].connect(database.db_info[args.database])
        app.config['web_domain'] = config.WEB_DOMAIN_DEV

    app.run(host='0.0.0.0', port=5000, threaded=False)
else:
    with app.app_context():    
        app.config['db_connection'] = database.Database()
        app.config['db_connection'].connect(database.db_info["prod"])
        app.config['web_domain'] = config.WEB_DOMAIN_PROD
