import logging
import json
import collections

from stc_session import StcSession
from stc_streamblock import StcStreamblock, StcStreamblockException
from stc_ethernetII import StcEthernetII
from stc_ipv4 import StcIPv4

log = logging.getLogger(__name__)

class StcConfig:
    def __init__(self):
        '''Create a new config instance. Internal config is seeed with teh defaults given by various
        classes.'''
        self._config = self.default()

    def default(self):
        return {
            StcIPv4.config_key: StcIPv4.default_config,
            StcEthernetII.config_key: StcEthernetII.default_config,
            StcStreamblock.config_key: StcStreamblock.default_config,
            StcSession.config_key: StcSession.default_config,
        }

    def apply_config(self, config):
        '''Apply the given config to internal configation of this instance.'''
        # internal "deep copy" function. 
        def _combine_dict(map1: dict, map2: dict):
            def update(d: dict, u: dict):
                for k, v in u.items():
                    if isinstance(v, collections.Mapping):
                        r = update(d.get(k, {}), v)
                        d[k] = r
                    else:
                        d[k] = u[k]
                return d

            _result = {}
            update(_result, map1)
            update(_result, map2)

            return _result
        
        # Now merge the dicts.
        self._config = _combine_dict(self._config, config)

    @property
    def data(self):
        '''Get the curret configuration of this instance.'''
        return self._config


if __name__ == '__main__':
    def pp(d):
        return json.dumps(d, indent=4, sort_keys=True)

    c = StcConfig()
    print('Default config: {}'.format(pp(c.default())))

    key = StcIPv4.config_key
    print('Default {}: {}'.format(key, pp(c.config[key])))
    newconf = {key: {'sourceAddr': '1.2.3.4', 'protocol': 123, 'Hello': 'World'}}
    c.apply_config(newconf)

    print('Updated {}: {}'.format(key, pp(c.config[key])))
