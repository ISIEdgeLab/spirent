#!/usr/bin/env python3 

import logging
from stcrestclient import stchttp
from stc_session import StcSession

log = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)

try:
    addr = StcSession.default_config['stc_server_addr']
    port = StcSession.default_config['stc_server_port']
    stc = stchttp.StcHttp(addr, port)

    sessions = stc.sessions()
    for session in sessions:
        log.info('Joining session {}'.format(session))
        stc.join_session(session)
        log.info('Ending session {}'.format(session))
        stc.end_session(session)

except Exception as e:
    print(e)
    exit(1)
