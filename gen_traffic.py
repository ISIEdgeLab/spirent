#!/usr/bin/env python3 

import logging
import json
import argparse 

from stc_session import StcSession
from stc_streamblock import StcStreamblock, StcStreamblockException
from stc_ethernetII import StcEthernetII
from stc_ipv4 import StcIPv4
from stc_config import StcConfig

log = logging.getLogger(__name__)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Start traffic between two enclaves.')
    ap.add_argument('-l', '--loglevel', choices=['all', 'debug', 'info', 'error', 'critical'],
                    dest='loglevel', default='info')
    ap.add_argument('--debugREST', default=False, help='If given, dump a lot of information about'
                    ' the HTTP/URL calls being made by the REST API.', action='store_true')
    ap.add_argument('-c', '--config', default=None, help='Customize the traffic via a config file.')
    ap.add_argument('--generate_config', default=False, help='Generate a sample config file to stdout and exit.',
                    action='store_true')
    ap.add_argument('-t', '--time-in-seconds', type=int, default=5, dest='howlong', 
                    help='How long to generate traffic for in seconds.')
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

    config = StcConfig()
    if args.generate_config:
        print(json.dumps(config.default(), indent=4, sort_keys=True))
        exit(0)

    # update default with passed in configuration.
    if args.config:
        with open(args.config) as fd:
            custom_config = json.load(fd)
            config.apply_config(custom_config)

    try:
        with StcSession(config=config) as sess:
            ports = sess.reserve_ports()
            try:
                sb = sess.create_streamblock(port=ports[0])
                sb.create_ethernetII()
                # GTL DEBUG
                log.debug('Streamblock FC before IPV4: {}'.format(sess.stc.get('streamblock1')['FrameConfig']))
                sb.create_ipv4()
                # GTL DEBUG
                log.debug('Streamblock FC after IPV4: {}'.format(sess.stc.get('streamblock1')['FrameConfig']))
                sb.generate_traffic(seconds=args.howlong)
            except StcStreamblockException as e:
                log.error('Error running traffic stream: {}'.format(e))
                exit(1)  
            
    except Exception as e:
        log.critical('Critical Error: {}'.format(e))
        raise(e)
        exit(2)

    exit(0)
