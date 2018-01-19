#!/usr/bin/env python

import logging
import json
from functools import wraps
from getpass import getuser
from random import choice
from string import ascii_lowercase as lowercase
from stcrestclient import stchttp
from stc_streamblock import StcStreamblock
from stc_ipv4 import StcIPv4

log = logging.getLogger(__name__)

def stc_connected(function):
    '''Check if this class instance is connected as a function decoration. Raises 
    StcSessionException on error.'''
    def _connection_check(self, *args, **kwargs):
        if not self._stc:
            raise StcSessionException('session does not exist.')
        elif not self._stc.started():
            raise StcSessionException('Session exists, but is not started.')
        elif 'project_handle' not in self._state:
            raise StcSessionException('No project associated with session.')
        # GTL - check here for chassis connection? If we do, it does another REST API
        # call which may not be worth it.

        return function(self, *args, **kwargs)

    return _connection_check

class StcSessionException(Exception):
    pass

class StcSession:   # py3.x inherits from object by default

    # class wide default config.
    default_config = {
        'stc_server_addr': '10.237.193.169',
        'stc_server_port': '8888',
        'chassis_addr': '10.237.192.20',
        'slot': 5,
    }
    config_key = 'stc_session'

    def __init__(self, config, state=None, user=None, verbose=False, keep_open=True):

        self._config = config.data[StcSession.config_key]
        self._stc_config = config
        self._state = state if state else self._config  # seed state with initial config settings.
        self._state['user'] = getuser() if not user else user
        if 'sid' not in self._state:
            self._state['sid'] = None
                                
        self._verbose = verbose

        self._stc = None
        self._objects = {}   # dict of handle to data. i.e. {'streamblock1': {sb data/config}, ...}
        self._state['keep_open'] = keep_open

    #
    # Context manager.
    #
    # There is a fair bit of context to save while using the spirent device (you can even
    # lock up ports on the device if things are not cleaned up properly. So keep track
    # of resources in a context manaager, err, context and cleanly delete and disconnect
    # when done with traffic.
    #
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type or exc_val or exc_tb:
            log.warning('exception caught in StcConnection context, disconnecting: {}, {}, {}, {}'.format(
                self.__class__, exc_type, exc_val, exc_tb))

        self.disconnect()
        return False

    @property
    def project_handle(self):
        if 'project_handle' not in self._state:
            return None

        return self._state['project_handle']

    #
    # Non context manager API. Connect to the chassis and stc REST API. If existing = False, 
    # create a session and project. If False, assume these already exist and do not create them.
    # a project.
    #
    def connect(self):
        addr, port = self._config['stc_server_addr'], self._config['stc_server_port']
        log.info('Connecting to: {}:{}'.format(addr, port))
        self._stc = stchttp.StcHttp(addr, port=port, debug_print=self._verbose)

        if self._state['sid']:
            log.info('Joining existing session {}'.format(self._state['sid']))
            self._stc.join_session(self._state['sid'])
        else:
            sid = ''.join([choice(lowercase) for i in range(10)])
            log.info('Creating new session, "{}" for user {}.'.format(sid, self._state['user']))
            self._state['sid'] = self._stc.new_session(self._state['user'], sid)

        self._stc.apply()

        chas_addr = self._state['chassis_addr']
        log.info('Connecting to chassis at {}'.format(chas_addr))
        # stc.connect wants a list of addresses for some reason.
        self._stc.connect([chas_addr])
        log.info('Connected.')

        # If not configured with an existing project, create a new one.
        if not self.project_handle:
            log.info('creating new project.')
            data = self._stc.createx('project')
            log.info('created project: {}'.format(json.dumps(data, indent=4, sort_keys=True)))
            self._state['project_handle'] = data['handle']

    @property
    def stc(self):
        return self._stc

    @property
    def config(self):
        return self._stc_config

    @stc_connected
    def disconnect(self):
        if self._state['keep_open']:
            log.info('Keeping session open...')
            return 

        if 'ports' in self._state and self._state['ports']:
            self.detach_ports()

        log.info('Deleting project {}.'.format(self.project_handle))
        self._stc.delete(self.project_handle)
        del self._state['project_handle']

        log.info('Ending session.')
        self._stc.end_session(end_tcsession=True)

    def keep_open(self, val=True):
        self._state['keep_open'] = val

    @stc_connected
    def reserve_ports(self):
        '''Reserve the ports that map to the source and destination configurations.'''
        # IP addresses map directly to port in our VERY VERY SPECIFIC setup. 
        # oh so dangerous:
        sport = self._stc_config.data[StcIPv4.config_key]['sourceAddr'].split('.')[1]
        dport = self._stc_config.data[StcIPv4.config_key]['destAddr'].split('.')[1]
        port_handles = []
        for p in [sport, dport]:
            # create a port and set the location. 
            location = '//{}/{}/{}'.format(self._state['chassis_addr'], self._state['slot'], p)
            h = self._stc.create('port', under=self.project_handle, location=location)
            port_handles.append(h)
            log.info('Created port "{}"'.format(h))
            log.debug('Port Data Pre-Attach: {}'.format(json.dumps(self._stc.get(h), indent=4, sort_keys=True)))

        log.info('Attaching to ports {}'.format(' '.join(port_handles)))
        self._stc.perform('AttachPorts', portList=' '.join(port_handles))

        for h in port_handles:
            log.debug('Port Data Post-Attach: {}'.format(json.dumps(self._stc.get(h), indent=4, sort_keys=True)))

        if 'ports' not in self._state:
            self._state['ports'] = []

        self._state['ports'] += port_handles

        return port_handles
    
    @stc_connected
    def create_obj(self, obj, under, *args, **kwargs):
        h = self._stc.create(obj, under, *args, **kwargs)
        data = self._stc.get(h)
        if 'obj_handles' not in self._state:
            self._state['obj_handles'] = []
        
        self._state['obj_handles'].append(h)
        log.debug('created {}:\n{}'.format(h, json.dumps(data, indent=4, sort_keys=True)))

        return h

    @stc_connected
    def create_streamblock(self, port):
        kwargs = self._stc_config.data[StcStreamblock.config_key]
        handle = self.create_obj('streamBlock', port, **kwargs)
        self._state['streamblock_handle'] = handle
        self._state['streamblock_port'] = port
        return StcStreamblock(handle, port, self)

    @stc_connected
    def destroy_streamblock(self):
        '''Destroy an existing streamblock. If active, the traffic in the streamblock will be stopped before destruction.'''
        handle = self._state['streamblock_handle'] if 'streamblock_handle' in self._config else None
        port = self._state['streamblock_port'] if 'streamblock_port' in self._config else None
        if handle and port:
            sb = StcStreamblock(handle, port, self)
            sb.stop_traffic()
            log.info('Deleting object {}/{}.'.format(handle, port))
            self._stc.delete(handle)
            del self._config['streamblock_handle']
            del self._config['streamblock_port']

    @stc_connected
    def detach_ports(self):
        if 'ports' not in self._state or not self._state['ports']:
            log.info('Attempt to detech from ports when we are not attached to any. Ignoring.')
            return

        ports = ' '.join(self._state['ports'])
        log.info('Detaching from ports: {}'.format(ports))
        self._stc.perform('DetachPorts', portlist=ports)

        for port in self._state['ports']:
            log.info('Deleting port {}'.format(port))
            self._stc.delete(port)

        del self._state['ports']

    @stc_connected
    def perform(self, command, params=None, **kwargs):
        data = self._stc.perform(command, params=params, **kwargs)
        log.info('performing {}({}, {})'.format(command, params, kwargs))
        log.debug('result: {}'.format(json.dumps(data, indent=4, sort_keys=True)))
        return data

    def save_and_write_session(self, filehandle):
        json.dump(self._state, filehandle, indent=4, sort_keys=True)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('urllib3').setLevel(logging.ERROR)   # quiet requests library.
    log.debug('testing StcSession class.')
    with StcSession() as s:
        ports = s.reserve_ports([8, 9])
        sb = s.create_streamblock(ports[0])
