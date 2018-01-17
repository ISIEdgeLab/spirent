#!/usr/bin/env python3 

import logging
import json
import argparse 

from stc_session import StcSession
from stc_config import StcConfig
from stc_ipv4 import StcIPv4
from stc_session import StcSession

log = logging.getLogger(__name__)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Create a configuration for use in other Edgelab Spirent scripts. Writes to stdout.')
    ap.add_argument('-s', '--srcaddr', default=None, required=True, help='Source address for traffic.', type=str)
    ap.add_argument('-d', '--dstaddr', default=None, required=True, help='Destination address for traffic.',
                    type=str)
    ap.add_argument('-t', '--traffic_duration', default=None, help='How long in seconds to generate traffic.', type=int)
    ap.add_argument('-p', '--protocol', default=17, help='IP protocol to use for traffic. Default is UDP (17).',
                    type=int)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO)

    config = StcConfig().data

    # IP config
    config[StcIPv4.config_key]['protocol'] = args.protocol
    config[StcIPv4.config_key]['destAddr'] = args.dstaddr
    config[StcIPv4.config_key]['sourceAddr'] = args.srcaddr
    # hardcoded for ilab. A.B.C.D --> A.B.C.1
    config[StcIPv4.config_key]['gateway'] = '.'.join(args.srcaddr.split('.')[:3]+['1'])

    # Session config
    if args.traffic_duration:
        config[StcSession.config_key]['traffic_duration'] = args.traffic_duration
   
    # write out config.
    print(json.dumps(config, indent=4, sort_keys=True))

    exit(0)
