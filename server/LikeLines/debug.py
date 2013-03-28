"""
Debug Blueprints.
"""
from flask import Blueprint, current_app, redirect, jsonify, url_for

debug_pages = Blueprint('debug', __name__)


@debug_pages.route("/clear_all")
def clear_all():
    mongo = current_app.mongo
    mongo.db.userSessions.remove()
    mongo.db.interactionSessions.remove()
    return redirect(url_for('destroy_session'))


@debug_pages.route("/dump")
def dump_session():
    mongo = current_app.mongo
    return jsonify({
        'userSessions': list(mongo.db.userSessions.find()),
        'interactionSessions': list(mongo.db.interactionSessions.find()),
    })
