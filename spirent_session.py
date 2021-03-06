#!/usr/bin/env python3 

import logging
import json
import argparse 
from os.path import isfile

from stc_session import StcSession, StcSessionException
from stc_streamblock import StcStreamblock, StcStreamblockException
from stc_ethernetII import StcEthernetII
from stc_ipv4 import StcIPv4
from stc_config import StcConfig

log = logging.getLogger(__name__)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Connect to Spirent device and start a new session and'
                                 ' reserve ports or connect to an existing session. Read or write session'
                                 ' information to the statefile given.')
    ap.add_argument('-l', '--loglevel', choices=['all', 'debug', 'info', 'error', 'critical'],
                    dest='loglevel', default='info')
    ap.add_argument('--debugREST', default=False, help='If given, dump a lot of information about'
                    ' the HTTP/URL calls being made by the REST API.', action='store_true')
    ap.add_argument('-s', '--statefile', type=str, dest='statefile', required=True, 
                    help='The spirent state file. If it does not exist, it will be created. The same state file'
                    ' should be passed to all invocations of this script for a given spirent session.')
    ap.add_argument('-c', '--configfile', dest='configfile', type=str, help='The configuration to use in this'
                    ' session. Defaults will be used to fill in any gaps in the configuration.', required=True)
    ap.add_argument('commands', choices=['create', 'traffic_start', 'traffic_stop', 'destroy'],
                    help='The command(s) to run using the given session/state. May be given multiple times. '
                    'Arguments will be processed in order.', nargs='+')
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
        with open(args.configfile) as fd:
            config.apply_config(json.load(fd))

        # load state
        if isfile(args.statefile):
            with open(args.statefile) as fd:
                state = json.load(fd)
        else:
            state = None

        try:
            with StcSession(config=config, state=state) as session:
                for command in args.commands:
                    if command == 'create':
                        # The "create" is done in the context manager if the session does not exist in the given state.
                        log.info('Created new session.')
                    
                    elif command == 'traffic_start':
                        ports = session.reserve_ports()
                        try:
                            sb = session.create_streamblock(port=ports[0])
                            sb.create_ethernetII()
                            sb.create_ipv4()
                            sb.start_traffic()
                        except StcStreamblockException as e:
                            log.error('Error starting traffic stream: {}'.format(e))
                            exit(1)  

                    elif command == 'traffic_stop':
                        try:
                            session.keep_open(False)
                            session.destroy_streamblock()
                            session.detach_ports()
                        except StcStreamblockException as e:
                            log.error('Error stapping traffic stream: {}'.format(e))
                            exit(1)  

                    elif command == 'destroy':
                        # in the "destroy" case, we do nothing and let the session context manager
                        # destory things when teh session goes out of scope.
                        session.keep_open(False)
                        log.info('Closing existing session/project/ports.')

                    else:
                        # should not happen as argparser restricts choices
                        raise('Command {} not supported.'.format(command))
                       
                    if command != 'destroy':
                        # pass the current stat forward.
                        with open(args.statefile, 'w') as fd:
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
