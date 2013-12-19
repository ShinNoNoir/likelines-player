# Simple CLI utility to download/upload/delete interactionSessions data to/from a LikeLines server
# License: MIT
# Author: Raynor Vliegendhart

import os, sys
import urllib, urllib2
import json

from optparse import OptionParser
from LikeLines.secretkey import compute_signature

VALID_COMMANDS = ['download', 'upload', 'delete']
COMMANDS_REQ_FILE = ['upload']

def get_optionparser():
    qualified_module_name = '%s.%s' % (__package__, os.path.splitext(os.path.basename(__file__))[0])
    usage = 'usage: python -m %s COMMAND VIDEO_ID [FILE]' % qualified_module_name
    usage += '\n\nValid COMMANDs: %s' % ', '.join(VALID_COMMANDS)
    
    parser = OptionParser(usage=usage)
    
    parser.add_option('-k',
                      dest='key',
                      metavar='KEY',
                      type='int',
                      help='Server key')
    
    parser.add_option('--kf',
                      dest='keyfile',
                      metavar='KEYFILE',
                      help='Server key file (e.g. .likelines_secret_key)')
    
    parser.add_option('-s',
                      dest='server',
                      metavar='SERVER',
                      help='LikeLines server')
    
    return parser

if __name__ == "__main__":
    parser = get_optionparser()
    options, args = parser.parse_args()
    
    if len(args) < 2:
        parser.print_help(file = sys.stderr)
        sys.exit(-1)
    
    serverkey = None
    serverkey_error = '-k or --kf flags are required'
    if options.key:
        serverkey = options.key
    elif options.keyfile:
        path = options.keyfile
        if os.path.exists(path):
            with open(path, 'r') as fh:
                serverkey = fh.readline().strip()
        else:
            serverkey_error = 'Cannot read key file: %s' % path
    
    if serverkey is None:
        print >>sys.stderr, serverkey_error
        sys.exit(-2)
    
    if not options.server:
        print >>sys.stderr, '-s flag is required'
        sys.exit(-3)
    
    cmd, videoId, interactionFile = (args + [None]*3)[:3]
    cmd = cmd.lower()
    if cmd not in VALID_COMMANDS:
        print >>sys.stderr, 'COMMAND is required'
        sys.exit(1)
    
    if not videoId:
        print >>sys.stderr, 'VIDEO_ID is required'
        sys.exit(2)
    
    if cmd in COMMANDS_REQ_FILE and interactionFile is None:
        print >>sys.stderr, 'FILE is required'
        sys.exit(3)
    
    url = options.server
    if not url.endswith('/'):
        url += '/'
    url += 'adminInteractions'
    
    payload = {
        'videoId': videoId,
        'cmd': cmd,
        'data': None
    }
    data = None
    if interactionFile is not None:
        with open(interactionFile,'r') as fh:
            data = json.load(fh)
    payload['data'] = data    
    
    serialized_payload = json.dumps(payload)
    sig = compute_signature(serverkey, serialized_payload)
    url += '?s=%s' % urllib.quote_plus(sig)
    
    print >>sys.stderr, 'Server request:'
    print >>sys.stderr, '-' * 40
    print >>sys.stderr, 'url:', url
    print >>sys.stderr, 'payload:'
    print >>sys.stderr, serialized_payload
    print >>sys.stderr, '-' * 40
    print >>sys.stderr
    
    print >>sys.stderr, 'Server response:'
    print >>sys.stderr, '-' * 40
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    try:
        response = urllib2.urlopen(req, serialized_payload)
        print response.read()
    except urllib2.HTTPError, e:
        print >>sys.stderr, e.read()


