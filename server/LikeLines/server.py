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

from flask import Flask, session, request, redirect, url_for, jsonify
from flask.ext.pymongo import PyMongo
from flaskutil import jsonp

import os, sys
import base64
import time
import uuid
import json
from functools import wraps
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
    
    return app

def create_db(app):
    mongo = PyMongo(app)
    return mongo

app = create_app()
mongo = create_db(app)

@app.before_request
def ensure_session():
    session.permanent = True
    if 'session_id' not in session:
        print >>sys.stderr, 'Creating new session'
        session_id = uuid.uuid4().hex
        session['session_id'] = session_id
        mongo.db.userSessions.insert(empty_session_object(session_id))
    else:
        print >>sys.stderr, 'Resuming previous session'
        session_id = session['session_id']

def empty_session_object(session_id):
    return {
        '_id':   session_id,
        'likes': {},
        'ts': time.time()
    }

def get_serverside_session(session_id=None):
    if session_id is None:
        session_id = session['session_id']
    return mongo.db.userSessions.find_one({'_id': session_id}) or empty_session_object(session_id)


@app.route('/createSession')
@jsonp
def LL_create_session():
    token = uuid.uuid4().hex
    videoId = request.args.get('videoId')
    ts = request.args.get('ts')
    session_id = session['session_id']
    
    mongo.db.interactionSessions.insert({
        '_id': token,
        'videoId': videoId,
        'ts': ts,
        'interactions': [],
        'userSession': session_id
    })
    mongo.db.interactionSessions.ensure_index('videoId')
    mongo.db.interactionSessions.ensure_index('userSession')
    
    return jsonify({'token': token})

@app.route('/sendInteractions')
@jsonp
def LL_send_interactions():
    error = None
    session_id = session['session_id']
    token = request.args.get('token')
    interactionSession = mongo.db.interactionSessions.find_one({'_id': token})
    if interactionSession:
        if interactionSession['userSession'] == session_id:
            interactions = json.loads( request.args.get('interactions') )
            mongo.db.interactionSessions.update({'_id': token}, {
                '$pushAll': {'interactions': interactions}
            })
            
            likes = []
            for ts, evtType, tc, last_tc in interactions:
                if evtType == 'LIKE':
                    likes.append(tc)
            
            if likes:
                mongo.db.userSessions.update({'_id': session_id}, {
                    '$pushAll': {'likes.%s' % (interactionSession['videoId']): likes}
                })
            
        else:
            error = 403
    else:
        error = 404
    
    return jsonify({'ok': 'ok'} if not error else {'error': error})


def processInteractionSession(interactions, playbacks, likedPoints):
    playback = []
    curStart = None
    last_tick = None
    last_last_tc = None
    
    for ts, evtType, tc, last_tc in sorted(interactions):
        if evtType == 'LIKE':
            likedPoints.append(tc)
        elif evtType == 'PLAYING':
            if curStart is not None:
                playback.append( (curStart, last_tc) )
            curStart = tc
        elif evtType == 'PAUSED':
            if curStart is not None:
                playback.append( (curStart, last_tc) )
                curStart = None
        
        last_last_tc = last_tc
    
    if curStart is not None and last_last_tc is not None:
        playback.append( (curStart, last_last_tc) )
    
    playbacks.append(playback)

@app.route('/aggregate')
@jsonp
def LL_aggregate():
    userSession = get_serverside_session()
    videoId = request.args.get('videoId')
    
    numSessions = 0
    playbacks = []
    seeks = None
    mca = None
    likedPoints = []
    
    myLikes = userSession['likes'].get(videoId, [])
    
    for interactionSession in mongo.db.interactionSessions.find({'videoId': videoId}):
        numSessions += 1
        processInteractionSession(interactionSession['interactions'], playbacks, likedPoints)
    
    aggregate = dict(numSessions=numSessions, playbacks=playbacks, seeks=seeks, mca=mca, likedPoints = likedPoints, myLikes=myLikes)
    return jsonify(aggregate)



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

@app.route("/clear_all")
def clear_all():
    mongo.db.userSessions.remove()
    mongo.db.interactionSessions.remove()
    return redirect(url_for('destroy_session'))

@app.route("/dump")
def dump_session():
    return jsonify({
        'userSessions': list(mongo.db.userSessions.find()),
        'interactionSessions': list(mongo.db.interactionSessions.find()),
    })



def _load_flask_secret_key():
    if not os.path.exists(SECRET_KEY_PATH):
        print >>sys.stderr, '*** Storing server secret key in "%s"...' % SECRET_KEY_PATH
        secret_key = base64.b64encode(os.urandom(KEY_STRENGTH))
        fh = open(SECRET_KEY_PATH, 'w')
        print >>fh, secret_key
        fh.close()
    else:
        fh = open(SECRET_KEY_PATH, 'r')
        secret_key = fh.readline().strip()
        fh.close()
    
    app.secret_key = secret_key


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
    _load_flask_secret_key()
    app.run(port = options.port, host=options.host)

