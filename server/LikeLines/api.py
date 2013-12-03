"""
Core API Blueprints. 
"""

from flask import Blueprint, current_app, jsonify, request
from flaskutil import jsonp

from usersession import get_session_id, get_serverside_session
from tokengen import generate_unique_token
from secretkey import compute_signature

import json

blueprint = Blueprint('api', __name__)


@blueprint.route('/createSession')
@jsonp
def LL_create_session():
    token = generate_unique_token()
    videoId = request.args.get('videoId')
    ts = request.args.get('ts')
    session_id = get_session_id()
    
    mongo = current_app.mongo
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


@blueprint.route('/sendInteractions')
@jsonp
def LL_send_interactions():
    mongo = current_app.mongo
    error = None
    session_id = get_session_id()
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



@blueprint.route('/aggregate')
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
    
    for interactionSession in current_app.mongo.db.interactionSessions.find({'videoId': videoId}):
        numSessions += 1
        processInteractionSession(interactionSession['interactions'], playbacks, likedPoints)
    
    mca = getMCAFromDB(videoId)
    
    aggregate = dict(numSessions=numSessions, playbacks=playbacks, seeks=seeks, mca=mca, likedPoints = likedPoints, myLikes=myLikes)
    return jsonify(aggregate)

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


def getMCAFromDB(videoId):
    mongo = current_app.mongo
    mca = mongo.db.mca.find_one({'_id': videoId})
    if mca:
        del mca['_id']
        for key in mca.keys():
            if key.startswith('mca-'):
                mca[key[4:]] = mca.pop(key)
    else:
        mca = {}
    
    return mca
                

@blueprint.route('/testKey', methods=['POST'])
def LL_testKey():
    try:
        data = json.loads(request.data)
        key = current_app.secret_key
        
        msg = data.get('msg','')
        their_sig = data.get('sig','')
        our_sig = compute_signature(key, msg)
        
        ok = our_sig == their_sig
        
        return jsonify({'ok': 'ok' if ok else 'no'}) 
        
    except ValueError, e:
        return jsonify({'error': e.message})



@blueprint.route('/postMCA', methods=['POST'])
def LL_postMCA():
    try:
        raw_data = request.data
        key = current_app.secret_key
        their_sig = request.args.get('s')
        our_sig = compute_signature(key, raw_data)
        
        ok = our_sig == their_sig
        
        if not ok:
            return jsonify({'ok': 'no'})
        
        #################################################
        
        data = json.loads(raw_data)
        
        videoId = data['videoId'] # string
        mcaName = data['mcaName'] # string
        mcaType = data['mcaType'] # "curve" | "point"
        mcaData = data['mcaData'] # double[]
        
        mongo = current_app.mongo
        mongo.db.mca.update({'_id': videoId}, {'$set': {
            'mca-%s' % mcaName: {
                'type': mcaType,
                'data': mcaData
            }
        }}, True)
        mongo.db.interactionSessions.ensure_index('mca')
        
        return jsonify({'ok': 'ok'}) 
        
    except ValueError, e:
        return jsonify({'error': e.message})

