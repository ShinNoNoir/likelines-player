"""
Flask utility functions.
"""

from functools import wraps, update_wrapper
from datetime import timedelta
from flask import make_response, request, current_app

# http://flask.pocoo.org/snippets/79/
def jsonp(func):
    """Wraps JSONified output for JSONP requests."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        callback = request.args.get('callback', False)
        if callback:
            data = str(func(*args, **kwargs).data)
            content = str(callback) + '(' + data + ')'
            mimetype = 'application/javascript'
            return current_app.response_class(content, mimetype=mimetype)
        else:
            return func(*args, **kwargs)
    return decorated_function

# http://flask.pocoo.org/snippets/56/
#  -> modified: origin=None is not a valid parameter value
def crossdomain(origin='*', methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, basestring):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, basestring):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator

# P3P circumvention
# e.g., see http://blogs.msdn.com/b/ieinternals/archive/2013/10/16/strict-p3p-validation-option-rejects-invalid-p3p-policies.aspx
def p3p(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        resp = make_response(func(*args, **kwargs))
        h = resp.headers
        h['P3P'] = 'CP="This is not a P3P policy! See //github.com/ShinNoNoir/likelines-player/blob/master/PRIVACY.txt for more info."'
        return resp
        
    return decorated_function
