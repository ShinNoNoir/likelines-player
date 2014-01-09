"""
Core API Blueprints. 
"""

from flask import Blueprint, current_app, jsonify, request
from flask import Response
from flaskutil import jsonp, crossdomain, p3p
from pymongo.errors import DuplicateKeyError

from usersession import get_session_id, get_serverside_session
from tokengen import generate_unique_token
from secretkey import compute_signature

import json

blueprint = Blueprint('api', __name__)


@blueprint.route('/createSession')
@crossdomain()
@p3p
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
@crossdomain()
@p3p
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
            tags = []
            for ts, evtType, tc, last_tc in interactions:
                if evtType == 'LIKE':
                    likes.append(tc)
                elif evtType.startswith('TAG_'):
                    tag = evtType[4:]
                    tags.append( [tc, tag] )
            
            if likes:
                mongo.db.userSessions.update({'_id': session_id}, {
                    '$pushAll': {'likes.%s' % (interactionSession['videoId']): likes}
                })
            
            if tags:
                mongo.db.userSessions.update({'_id': session_id}, {
                    '$pushAll': {'tags.%s' % (interactionSession['videoId']): tags}
                })
            
        else:
            error = 403
    else:
        error = 404
    
    return jsonify({'ok': 'ok'} if not error else {'error': error})



@blueprint.route('/aggregate')
@crossdomain()
@p3p
@jsonp
def LL_aggregate():
    userSession = get_serverside_session()
    videoId = request.args.get('videoId')
    
    numSessions = 0
    playbacks = []
    seeks = None
    mca = None
    likedPoints = []
    taggedPoints = []
    
    myLikes = userSession['likes'].get(videoId, [])
    
    for interactionSession in current_app.mongo.db.interactionSessions.find({'videoId': videoId}):
        numSessions += 1
        processInteractionSession(interactionSession['interactions'], playbacks, likedPoints, taggedPoints)
    
    mca = getMCAFromDB(videoId)
    
    aggregate = dict(numSessions=numSessions, playbacks=playbacks, seeks=seeks, mca=mca, likedPoints = likedPoints, myLikes=myLikes, taggedPoints=taggedPoints)
    return jsonify(aggregate)

def processInteractionSession(interactions, playbacks, likedPoints, taggedPoints):
    playback = []
    curStart = None
    prev_tick = None
    prev_last_tc = None
    prev_ts = None
    prev_tc = None
    
    for curInteraction in sorted(interactions):
        ts, evtType, tc, last_tc = curInteraction
        if evtType == 'LIKE':
            likedPoints.append(tc)
        elif evtType.startswith('TAG_'):
            tag = evtType[4:]
            taggedPoints.append( (tc, tag) )
            
        elif evtType == 'PLAYING':
            if curStart is not None:
                playback.append( (curStart, last_tc) )
            curStart = tc
        elif evtType == 'PAUSED':
            if curStart is not None:
                playback.append( (curStart, last_tc) )
                curStart = None
        
        # issue 16
        # Arbitrary factor: 30
        elif evtType == 'TICK':
            if prev_ts is not None and prev_tc is not None and (ts-prev_ts)*30 < (tc-prev_tc):
                # Treat this as a skip and end the current interval
                if curStart is not None:
                    playback.append( (curStart, prev_tc) )
                    curStart = tc
        
        prev_ts = ts
        prev_tc = tc
        prev_last_tc = last_tc
    
    if curStart is not None and prev_last_tc is not None:
        playback.append( (curStart, prev_last_tc) )
    
    # only add non-empty playbacks
    if playback:
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
            return jsonify({'ok': 'no', 'their_sig': their_sig, 'our_sig': our_sig})
        
        #################################################
        
        data = json.loads(raw_data)
        
        videoId = data['videoId'] # string
        mcaName = data['mcaName'] # string
        
        delete = data.get('delete', False) == True
        
        mongo = current_app.mongo
        if not delete:
            mcaType = data['mcaType'] # "curve" | "point"
            mcaData = data['mcaData'] # double[]
            mcaWeight = data.get('mcaWeight', 1.0)
            
            mongo.db.mca.update({'_id': videoId}, {'$set': {
                'mca-%s' % mcaName: {
                    'type': mcaType,
                    'data': mcaData,
                    'weight': mcaWeight
                }
            }}, True)
            mongo.db.interactionSessions.ensure_index('mca')
        
        else:
            mongo.db.mca.update({'_id': videoId}, {'$unset': {
                'mca-%s' % mcaName: ""
            }})
            
        
        return jsonify({'ok': 'ok'}) 
        
    except ValueError, e:
        return jsonify({'error': e.message})


@blueprint.route('/adminInteractions', methods=['POST'])
def LL_adminInteractions():
    def jsonify2(x):
        return jsonify(x) if isinstance(x, dict) else Response(json.dumps(x, indent=2),  mimetype='application/json')
    
    try:
        raw_data = request.data
        key = current_app.secret_key
        their_sig = request.args.get('s')
        our_sig = compute_signature(key, raw_data)
        
        ok = our_sig == their_sig
        
        if not ok:
            return jsonify({'ok': 'no', 'their_sig': their_sig, 'our_sig': our_sig})
        
        #################################################
        
        data = json.loads(raw_data)
        
        videoId = data['videoId'] # string
        cmd = data['cmd'].lower() # "download" | "upload" | "delete"
        interactionSessions = data.get('data') # json? 
        
        mongo = current_app.mongo
        
        res = None
        if cmd == 'download':
            res = []
            for interactionSession in mongo.db.interactionSessions.find({'videoId': videoId}):
                res.append(interactionSession)
        
        elif cmd == 'upload':
            dups = []
            wrongid = []
            
            for interactionSession in interactionSessions:
                _id = interactionSession['_id']
                if interactionSession['videoId'] != videoId:
                    wrongid.append(_id)
                    continue
                
                try:
                    mongo.db.interactionSessions.insert(interactionSession)
                except DuplicateKeyError:
                    dups.append(_id)
                    
            res = {'ok': 'ok'}
            if dups or wrongid:
                res['skipped'] = {}
                if dups:
                    res['skipped']['duplicates'] = dups
                if wrongid:
                    res['skipped']['wrong_videoid'] = wrongid
        
        elif cmd == 'delete':
            mongo.db.interactionSessions.remove({'videoId': videoId})
            res = {'ok': 'ok'}
        
        return jsonify2(res)
        
    except ValueError, e:
        return jsonify({'error': e.message})

