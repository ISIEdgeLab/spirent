import logging

log = logging.getLogger(__name__)

class StcIpv4Exception(Exception):
    pass

class StcIPv4:

    default_config = {
        "checksum": 0,
        "destAddr": "10.9.1.25",
        "destPrefixLength": 24,
        "fragOffset": 0,
        "gateway": "10.8.1.1",
        "identification": 0,
        "ihl": 5,
        "prefixLength": 24,
        "protocol": 17,
        "sourceAddr": "10.8.1.25",
        "totalLength": 20,
        "ttl": 255,
    }
    config_key = 'ipv4'

    def __init__(self):
        pass
