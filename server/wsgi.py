"""
dotCloud wsgi file.
"""

import sys
import json
sys.path.append('/home/dotcloud/current')
with open('/home/dotcloud/environment.json') as fh:
    env = json.load(fh)
    
from LikeLines.server import create_app, create_db 
from LikeLines.usersession import get_session_id
from LikeLines.secretkey import load_secret_key
from LikeLines.debug import debug_pages


from flask import session, request, redirect, url_for

dotcloud_config = {
    'MONGO_DBNAME': 'admin', # TODO: change this to something configurable
    
    'MONGO_HOST': env['DOTCLOUD_DB_MONGODB_HOST'],
    'MONGO_PORT': env['DOTCLOUD_DB_MONGODB_PORT'],
    
    'MONGO_USERNAME': env['DOTCLOUD_DB_MONGODB_LOGIN'],
    'MONGO_PASSWORD': env['DOTCLOUD_DB_MONGODB_PASSWORD']
}

app = create_app(dotcloud_config)
app.mongo = create_db(app)

@app.route("/")
def index():
    return "LikeLines Backend server. Your user session id: %s" % get_session_id()

@app.route("/end_session")
def end_session():
    # throws away (client-side) session information
    del session['session_id']
    url = request.args.get('redirect', url_for('index'))
    return redirect(url)

#app.register_blueprint(debug_pages)
load_secret_key('/home/dotcloud/current/.likelines_secret_key', app)

application = app
