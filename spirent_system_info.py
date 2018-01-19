#!/usr/bin/env python3 

import logging
import argparse 
import json

from stc_session import StcSession
from stc_config import StcConfig

log = logging.getLogger(__name__)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Show Sprient system info.')
    ap.add_argument('-l', '--loglevel', choices=['all', 'debug', 'info', 'error', 'critical'],
                    dest='loglevel', default='info')
    args = ap.parse_args()

    logging.basicConfig(level=args.loglevel.upper())
    config = StcConfig()
    with StcSession(config, state=None, keep_open=False) as ss:
        data = ss.stc.system_info()
        print('System Info: {}'.format(json.dumps(data, indent=4, sort_keys=True)))
        data = ss.stc.server_info()
        print('Server info: {}'.format(json.dumps(data, indent=4, sort_keys=True)))
        data = ss.stc.chassis_info(config.data[StcSession.config_key]['chassis_addr'])
        print('Chassis info: {}'.format(json.dumps(data, indent=4, sort_keys=True)))

        print("Existing sessions:")
        for session in ss.stc.sessions():
            print('\t{}'.format(session))

    exit(0)
