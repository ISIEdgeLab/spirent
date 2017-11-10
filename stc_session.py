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
        elif not self._project_handle:
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

    def __init__(self, config, user=None, sid=None, verbose=False):
        self._config = config.data[StcSession.config_key]
        self._stc_config = config
        self._user = getuser() if not user else user
        self._sid = None    # The session id according to Spirent, which is a 
                            # string of the format "sessname - userid"
        self._verbose = verbose
        if sid:
            self._session_id = sid
        else:
            self._session_id = ''.join([choice(lowercase) for i in range(10)])

        self._stc = None
        self._project_handle = None
        self._ports = {}
        self._objects = {}   # dict of handle to data. i.e. {'streamblock1': {sb data/config}, ...}

    #
    # Context manager.
    #
    # There is a fair bit of context to save while using the spirent device (you can even
    # lock up ports on the device if things are not cleaned up properly. So keep track
    # of resources in a context manaager, err, context and cleanly delete and disconnect
    # when done with traffic.
    #
    def __enter__(self):
        self._stc = self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type or exc_val or exc_tb:
            log.warning('exception caught in StcConnection context, disconnecting: {}, {}, {}, {}'.format(
                self.__class__, exc_type, exc_val, exc_tb))

        self.disconnect()
        return False

    @property
    def project_handle(self):
        return self._project_handle

    #
    # Non context manager API. Create a session, connect to the chassis. an create
    # a project.
    #
    def connect(self):
        addr, port = self._config['stc_server_addr'], self._config['stc_server_port']
        log.info('Connecting to: {}:{}'.format(addr, port))
        stc = stchttp.StcHttp(addr, port=port, debug_print=self._verbose)

        log.info('Creating new session, "{}" for user {}.'.format(self._session_id, self._user))
        self._sid = stc.new_session(self._user, self._session_id)

        stc.apply()

        chas_addr = self._config['chassis_addr']
        log.info('Connecting to chassis at {}'.format(chas_addr))
        stc.connect(chas_addr)
        log.info('Connected.')

        log.info('creating new project.')
        data = stc.createx('project')
        log.info('created project: {}'.format(json.dumps(data, indent=4, sort_keys=True)))
        self._project_handle = data['handle']

        return stc

    @property
    def stc(self):
        return self._stc

    @property
    def config(self):
        return self._stc_config

    @stc_connected
    def disconnect(self):
        if self._ports:
            ports = ' '.join(self._ports.keys())
            log.info('Detaching from ports: {}'.format(ports))
            self._stc.perform('DetachPorts', portlist=ports)

        log.info('Deleting {} created objects.'.format(len(self._objects)))
        for h in self._objects.keys():
            log.info('Deleting object {}.'.format(h))
            # GTL - no idea why some things that we create() are not found on delete(). Ugh.
            try:
                self._stc.delete(h) 
            # except RestHttpError as e:   stc rest should raise a locally importable symbol. GTL FIX.
            except Exception as e:
                log.warning('Error deleting stc object: {}'.format(e))

        log.info('Deleting project {}.'.format(self._project_handle))
        self._stc.delete(self._project_handle)

        log.info('Ending session.')
        self._stc.end_session(end_tcsession=True)

    #
    # methods
    #
    @stc_connected
    def reserve_ports(self):
        '''Reserve the ports that map to the source and destination configurations.'''
        # IP addresses map directly to port in our VERY VERY SPECIFIC setup. 
        # oh so dangerous:
        sport = self._stc_config.data[StcIPv4.config_key]['sourceAddr'].split('.')[1]
        dport = self._stc_config.data[StcIPv4.config_key]['destAddr'].split('.')[1]
        new_ports = []
        for p in [sport, dport]:
            # create a port and set the location. 
            location = '//{}/{}/{}'.format(self._config['chassis_addr'], self._config['slot'], p)
            h = self._stc.create('port', under=self._project_handle, location=location)
            new_ports.append(h)
            self._ports[h] = self._stc.get(h)
            log.info('Created port "{}"'.format(h))
            log.debug('Port Data Pre-Attach: {}'.format(json.dumps(self._ports[h], indent=4, sort_keys=True)))

        self._stc.perform('AttachPorts', portList=' '.join(new_ports))
        for h in new_ports:
            self._ports[h] = self._stc.get(h)
            log.debug('Port Data Post-Attach: {}'.format(json.dumps(self._ports[h], indent=4, sort_keys=True)))

        return new_ports
    
    @stc_connected
    def create_obj(self, obj, under, *args, **kwargs):
        h = self._stc.create(obj, under, *args, **kwargs)
        data = self._stc.get(h)
        self._objects[h] = data
        log.debug('created {}:\n{}'.format(h, json.dumps(data, indent=4, sort_keys=True)))
        return h

    @stc_connected
    def create_streamblock(self, port):
        kwargs = self._stc_config.data[StcStreamblock.config_key]
        handle = self.create_obj('streamBlock', port, **kwargs)
        return StcStreamblock(handle, port, self)

    @stc_connected
    def perform(self, command, params=None, **kwargs):
        data = self._stc.perform(command, params=params, **kwargs)
        log.info('performing {}({}, {})'.format(command, params, kwargs))
        log.debug('result: {}'.format(json.dumps(data, indent=4, sort_keys=True)))
        return data

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('urllib3').setLevel(logging.ERROR)   # quiet requests library.
    log.debug('testing StcSession class.')
    with StcSession() as s:
        ports = s.reserve_ports([8, 9])
        sb = s.create_streamblock(ports[0])
