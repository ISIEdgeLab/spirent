import logging
from sys import maxsize
from time import sleep

from stc_ipv4 import StcIPv4
from stc_ethernetII import StcEthernetII

log = logging.getLogger(__name__)

class StcStreamblockException(Exception):
    pass

class StcStreamblock:

    default_config = {
        "AdvancedInterleavingGroup": "0",
        "AllowInvalidHeaders": False,
        "BurstSize": "1",
        "ByPassSimpleIpSubnetChecking": False,
        "ConstantFillPattern": "0",
        "CustomPfcPriority": "0",
        "EnableBackBoneTrafficSendToSelf": True,
        "EnableBidirectionalTraffic": False,
        "EnableControlPlane": False,
        "EnableCustomPfc": False,
        "EnableFcsErrorInsertion": False,
        "EnableHighSpeedResultAnalysis": True,
        "EnableResolveDestMacAddress": True,
        "EnableStreamOnlyGeneration": True,
        "EnableTxPortSendingTrafficToSelf": False,
        "EndpointMapping": "ONE_TO_ONE",
        "FillType": "CONSTANT",
        "Filter": "",
        "FixedFrameLength": "128",
        "FrameConfig": "",
        "FrameLengthMode": "FIXED",
        "InsertSig": True,
        "InterFrameGap": "12",
        "Load": "10",
        "LoadUnit": "PERCENT_LINE_RATE",
        "MaxFrameLength": "256",
        "MinFrameLength": "128",
        "Priority": "0",
        "ShowAllHeaders": False,
        "StartDelay": "0",
        "StepFrameLength": "1",
        "TimeStampOffset": "0",
        "TimeStampType": "MIN",
        "TrafficPattern": 'PAIR'
    }
    config_key = 'streamblock'

    def __init__(self, handle, port_handle, session):
        self._handle = handle
        self._port_handle = port_handle
        self._session = session
        self._config = session.config.data[StcStreamblock.config_key]

    def create_ethernetII(self, **kwargs):
        # GTL - not sure why giving args to ethII causes things to break...
        # GTL - look into this.
        # kwargs = self._session.config.data[StcEthernetII.config_key]
        # return self._session.create_obj('Ethernet:EthernetII', self._handle, None, **kwargs)
        return self._session.create_obj('Ethernet:EthernetII', self._handle)

    def create_ipv4(self, **kwargs):
        kwargs = self._session.config.data[StcIPv4.config_key]
        return self._session.create_obj('ipv4:IPv4', self._handle, None, **kwargs)

    def generate_traffic(self, seconds=0):
        '''
        Given this stream block, generate traffic via our session for the time given.

        This method will block until the the time has passed. If seconds is zero, it will
        block for a very long time.

        StcStreamblockException raised on errors. True returned on sucess.

        '''
        t = seconds if seconds else maxsize

        # GTL is this needed?
        self._session.stc.apply()

        generator = self._session.stc.get(self._port_handle, 'children-generator')  # ugh. just ugh.

        # stop to get to known state
        log.info('Stopping generator to get to known state.')
        self._session.perform('GeneratorStop', generatorlist=generator)

        # do ARP
        log.info('Doing ARP to resolve gateway addresses.')
        self._session.perform('ArpNDStart', handlelist=self._handle)
        status = self._session.perform('ArpNDVerifyResolved', handlelist=self._handle)
        if not status:
            raise StcStreamblockException('Error when getting ARP response status.')

        if 'PassFailState' not in status or status['PassFailState'] != 'PASSED':
            raise StcStreamblockException('ARP failed. Status: {}'.format(status))

        log.info('Starting streamblock {}'.format(self._handle))
        status = self._session.perform('StreamBlockStart', streamblocklist=self._handle)

        log.info('Sleeping {} seconds'.format(t))
        sleep(seconds)

        log.info('Stopping streamblock {}'.format(self._handle))
        status = self._session.perform('StreamBlockStop', streamblocklist=self._handle)

        return True
