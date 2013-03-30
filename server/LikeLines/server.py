# Simple reference implementation for LikeLines backend
# License: MIT
# Author: Raynor Vliegendhart

# Future features to be implemented:
#  * Notion of "users" s.t. multiple sessions can be linked to a single user 
#

APP_NAME = 'LikeLines Server'
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 9090
SECRET_KEY_PATH = '.likelines_secret_key'
KEY_STRENGTH = 24

from flask import Flask, session, request, redirect, url_for
from flask.ext.pymongo import PyMongo

from debug import debug_pages
from usersession import ensure_session
import api

from secretkey import load_secret_key

import os, sys
import base64
from optparse import OptionParser

default_config = {
    'PERMANENT_SESSION_LIFETIME': 365*24*60*60,
    
    'MONGO_HOST': 'localhost',
    'MONGO_PORT': '27017',
    
    'MONGO_USERNAME': None,
    'MONGO_PASSWORD': None,
    
    'MONGO_DBNAME': 'LikeLinesDB'
}

def create_app():
    app = Flask(__name__)
    app.name = APP_NAME
    app.debug = True
    
    app.config.update(default_config)
    app.before_request(ensure_session)
    app.register_blueprint(api.blueprint)
    
    return app

def create_db(app):
    mongo = PyMongo(app)
    return mongo

app = create_app()
app.mongo = create_db(app)


@app.route("/")
def index():
    ensure_session()
    return "LikeLines Backend server. Your user session id: %s" % session.get('session_id','--')

@app.route("/end_session")
def end_session():
    # throws away (client-side) session information
    del session['session_id']
    url = request.args.get('redirect', url_for('index'))
    return redirect(url)

app.register_blueprint(debug_pages)


def get_optionparser():
    qualified_module_name = '%s.%s' % (__package__, os.path.splitext(os.path.basename(__file__))[0])
    parser = OptionParser(usage='usage: python -m %s [OPTION]' % qualified_module_name)
    parser.add_option('-p',
                      dest='port',
                      metavar='PORT',
                      type='int',
                      default=DEFAULT_PORT,
                      help='Listen port (default: %s)' % DEFAULT_PORT)
    
    parser.add_option('-b',
                      dest='host',
                      metavar='IP',
                      default=DEFAULT_HOST,
                      help='Listen ip (default: %s)' % DEFAULT_HOST)
    
    return parser

if __name__ == "__main__":
    options, _ = get_optionparser().parse_args()
    load_secret_key(app, SECRET_KEY_PATH)
    app.run(port = options.port, host=options.host)

