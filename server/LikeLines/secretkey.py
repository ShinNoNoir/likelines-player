"""
Management of generating and loading secret keys.
"""

KEY_STRENGTH = 24

import os
import sys
import base64

from hashlib import sha1
from hmac import new as hmac

def generate_secret_key():
    return base64.b64encode(os.urandom(KEY_STRENGTH))
    
def load_secret_key(path, app=None):
    if not os.path.exists(path):
        print >>sys.stderr, '*** Storing server secret key in "%s"...' % path
        secret_key = generate_secret_key()
        fh = open(path, 'w')
        print >>fh, secret_key
        fh.close()
    else:
        fh = open(path, 'r')
        secret_key = fh.readline().strip()
        fh.close()
    
    if app is not None:
        app.secret_key = secret_key

def compute_signature(key, msg):
    return "%s" % hmac(key, msg, sha1).digest().encode('base64')[:-1]

if __name__ == '__main__':
    print generate_secret_key()

