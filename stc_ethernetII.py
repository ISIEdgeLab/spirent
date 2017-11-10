import logging

log = logging.getLogger(__name__)

class StcEthernetIIException(Exception):
    pass

class StcEthernetII:

    default_config = {
        ## "Active": "true",
        ## "Name": "ethernet_2872",
        ## "dstMac": "00:00:01:00:00:01",
        "etherType": "88B5",
        ## "parent": "streamblock1",
        ## "preamble": "55555555555555d5",
        ## "srcMac": "00:10:94:00:00:02"
    }
    config_key = 'ethernetII'

    def __init__(self):
        pass
