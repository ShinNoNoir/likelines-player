# Simple CLI utility to upload MCA data to a LikeLines server
# License: MIT
# Author: Raynor Vliegendhart

import os, sys
import urllib, urllib2
import json

from optparse import OptionParser
from LikeLines.secretkey import compute_signature

OP_UPLOAD, OP_DELETE = range(2)
VALID_MCA_TYPES = ['curve', 'point']

def get_optionparser():
    qualified_module_name = '%s.%s' % (__package__, os.path.splitext(os.path.basename(__file__))[0])
    parser = OptionParser(usage='usage: python -m %s VIDEO_ID MCA_NAME [MCA_TYPE MCA_FILE] [OPTION]' % qualified_module_name)
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
    
    parser.add_option('-d',
                      dest='delete',
                      action='store_true',
                      default=False,
                      help='Delete MCA')
    
    return parser

def read_mca_file(path):
    if os.path.exists(path):
        res = []
        with open(path, 'r') as fh:
            for line in fh:
                line = line.strip()
                if line.startswith('#'):
                    continue
                x = float(line)
                res.append(x)
        return res
    else:
        return False

def http_post(url, payload):
    pass

if __name__ == "__main__":
    parser = get_optionparser()
    options, args = parser.parse_args()
    
    if len(args) == 0:
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
        sys.exit(1)
    
    operation = OP_UPLOAD
    videoId, mcaName, mcaType, mcaFile = (args + [None]*4)[:4]
    mcaData = None
    mcaWeight = 1.0
    
    if options.delete:
        operation = OP_DELETE
    
    if not videoId:
        print >>sys.stderr, 'VIDEO_ID is required'
        sys.exit(1)
        
    if not mcaName:
        print >>sys.stderr, 'MCA_NAME is required'
        sys.exit(2)
    
    url = options.server
    if not url.endswith('/'):
        url += '/'
    url += 'postMCA'
    
    payload = {
        'videoId': videoId,
        'mcaName': mcaName,
    }
    
    if operation == OP_UPLOAD:
        if not mcaType:
            print >>sys.stderr, 'MCA_TYPE is required'
            sys.exit(3)
        else:
            if mcaType not in VALID_MCA_TYPES:
                print >>sys.stderr, 'MCA_TYPE must be one of: %s' % ', '.join(VALID_MCA_TYPES)
                sys.exit(3)
            
            payload['mcaType'] = mcaType
        
        if not mcaFile:
            print >>sys.stderr, 'MCA_FILE is required'
            sys.exit(4)
        else:
            mcaData = read_mca_file(mcaFile)
            if mcaData is False:
                print >>sys.stderr, 'Cannot read MCA file: %s' % mcaFile
                sys.exit(4)
            
            payload['mcaData'] = mcaData
        
        payload['mcaWeight'] = mcaWeight
        
    elif operation == OP_DELETE:
        payload['delete'] = True
    
    serialized_payload = json.dumps(payload)
    sig = compute_signature(serverkey, serialized_payload)
    url += '?s=%s' % urllib.quote_plus(sig)
    
    print 'Server request:'
    print '-' * 40
    print 'url:', url
    print 'payload:'
    print serialized_payload
    print '-' * 40
    print
    
    print 'Server response:'
    print '-' * 40
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    try:
        response = urllib2.urlopen(req, serialized_payload)
        print response.read()
    except urllib2.HTTPError, e:
        print e.read()


