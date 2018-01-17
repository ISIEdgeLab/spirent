#!/usr/bin/env python3 

import logging
import json
import argparse 
from sys import stdout as STDOUT, stdin as STDIN
from contextlib import contextmanager
from os.path import exists as file_exists

from stc_session import StcSession, StcSessionException
from stc_streamblock import StcStreamblock, StcStreamblockException
from stc_ethernetII import StcEthernetII
from stc_ipv4 import StcIPv4
from stc_config import StcConfig

log = logging.getLogger(__name__)

@contextmanager
def open_file_or_stdio(filename, stdio):
    '''Context manager for file handle. If given '-' return stdio, else open file. If STDOUT is given, 
    the file handle will be write only, if STDIN it will be readonly.'''
    if filename and filename != '-':
        mode = 'w' if stdio is STDOUT else 'r'
        fd = open(filename, mode)
    else:
        fd = stdio

    try:
        yield fd
    finally:
        if fd is not stdio:
            fd.close()

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Connect to Spirent device and start a new session and'
                                 ' reserve ports or connect to an existing session. Read or write session'
                                 ' information to the statefile given.')
    ap.add_argument('-l', '--loglevel', choices=['all', 'debug', 'info', 'error', 'critical'],
                    dest='loglevel', default='info')
    ap.add_argument('--debugREST', default=False, help='If given, dump a lot of information about'
                    ' the HTTP/URL calls being made by the REST API.', action='store_true')
    ap.add_argument('-s', '--statefile', type=str, default='-', dest='statefile',
                    required=True, help='Write Spirent session state to this file. This state will be '
                    'used when modifying traffic flows. The argument can be "-". If it is, the state '
                    'will be written to stdout when creating or read from stdin when destroying. "-" is '
                    'the default.')
    ap.add_argument('--command', required=True, choices=['create', 'traffic_start', 'traffic_stop', 'destroy'],
                    dest='command', help='The command to run using the given session/state.')
    args = ap.parse_args()

    if args.debugREST:
        requests_log = logging.getLogger("urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True
        import http.client as http_client
        http_client.HTTPConnection.debuglevel = 1
    else:
        logging.getLogger("urllib3").setLevel(logging.ERROR)

    logging.basicConfig(level=args.loglevel.upper())

    try:
        config = StcConfig()

        # update default with passed in state.
        if file_exists(args.statefile):
            with open_file_or_stdio(args.statefile, STDIN) as fd:
                custom_config = json.load(fd)
                config.apply_config(custom_config)

        try:
            with StcSession(config=config) as session:
                if args.command == 'create':
                    # The "create" is done in the context manager if the session does not exist in the given state.
                    session.keep_open()
                
                elif args.command == 'traffic_start':
                    session.keep_open()
                    ports = session.reserve_ports()
                    try:
                        sb = session.create_streamblock(port=ports[0])
                        sb.create_ethernetII()
                        sb.create_ipv4()
                        sb.start_traffic()
                    except StcStreamblockException as e:
                        log.error('Error starting traffic stream: {}'.format(e))
                        exit(1)  

                elif args.command == 'traffic_stop':
                    try:
                        session.keep_open()
                        session.destroy_streamblock()
                        session.detach_ports()
                    except StcStreamblockException as e:
                        log.error('Error stapping traffic stream: {}'.format(e))
                        exit(1)  

                elif args.command == 'destroy':
                    # in the "destroy" case, we do nothing and let the session context manager
                    # destory things when teh session goes out of scope.
                    log.info('Closing existing session/project/ports.')

                else:
                    # should not happen as argparser restricts choices
                    raise('Command {} not supported.'.format(args.command))
                   
                if args.command in ['create', 'traffic_start', 'traffic_stop']:
                    # pass the current stat forward.
                    with open_file_or_stdio(args.statefile, STDOUT) as fd:
                        session.save_and_write_session(fd)

        except StcSessionException as e:
            log.critical('Critical StcSession Error: {}'.format(e))
            raise(e)
            exit(100)

    except Exception as e:
        log.critical('Critical General Error: {}'.format(e))
        raise(e)
        exit(2)

    exit(0)
