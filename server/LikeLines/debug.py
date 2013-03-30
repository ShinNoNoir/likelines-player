"""
Debug Blueprints.
"""
from flask import Blueprint, current_app, redirect, jsonify, url_for, request

debug_pages = Blueprint('debug', __name__)


@debug_pages.route("/clear_all", methods=['GET', 'POST'])
def clear_all():
    if request.method == 'GET':
        return '<form method="POST"><input type="submit" value="CLEAR DATABASE"></form>'
    else:
        mongo = current_app.mongo
        mongo.db.userSessions.remove()
        mongo.db.interactionSessions.remove()
        return redirect(url_for('end_session'))


@debug_pages.route("/dump")
def dump_session():
    mongo = current_app.mongo
    return jsonify({
        'userSessions': list(mongo.db.userSessions.find()),
        'interactionSessions': list(mongo.db.interactionSessions.find()),
    })
