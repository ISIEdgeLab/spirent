#!/usr/bin/env bash

# "hardcoded" values
CHASSIS=${CHASSIS:-"10.237.192.20"}
STCERV=${STCERV:="10.237.193.169:8888"}
SESSID=${SESSID:-RestSession1}
USERID=${USERID:-tuser}

# user args.
TRAF_SRCADDR=${TRAF_SRCADDR:-10.8.1.25}
TRAF_DSTADDR=${TRAF_DSTADDR:-10.9.1.25}
TRAF_IPPROTO=${TRAF_IPPROTO:-17}
TRAF_FRAMELEN=${TRAF_FRAMELEN:-128}
TRAF_FRAMEPERSEC=${TRAF_FRAMEPERSEC:-10}
TRAF_TIME=${TRAF_TIME:-5}

while getopts s:d:p:l:r:t:h opt; do
    case $opt in
        s) TRAF_SRCADDR=${OPTARG}
            echo source address set to ${TRAF_SRCADDR}
            ;;
        d) TRAF_DSTADDR=${OPTARG}
            echo destination address set to ${TRAF_DSTADDR}
            ;;
        p) TRAF_IPPROTO=${OPTARG}
            echo IP protocol set to ${TRAF_IPPROTO}
            ;;
        l) TRAF_FRAMELEN=${OPTARG}
            echo Frame length set to ${TRAF_FRAMELEN}
            ;;
        r) TRAF_FRAMEPERSEC=${OPTARG}
            echo Frames per second set to ${TRAF_FRAMEPERSEC}
            ;;
        t) TRAF_TIME=${OPTARG}
            echo Traffic will run for ${TRAF_TIME} seconds.
            ;;
        ?)
            echo
            echo $(basename $0) -s source_addr -d dest_addr -p IP_protocol -l frame_len -r frames_per_second -t time_to_run
            echo
            echo source_addr can also be set via \$TRAF_SRCADDR in the environment.
            echo dest_addr can also be set via \$TRAF_DSTADDR in the environment.
            echo IP_protocol can also be set via \$TRAF_IPPROTO in the environment.
            echo frame_len can also be set via \$TRAF_FRAMELEN in the environment.
            echo frames_per_second can also be set via \$TRAF_FRAMEPERSEC in the environment.
            echo time_to_run can also be set via \$TRAF_TIME in the environment.
            echo 
            echo The addresses will control which enclave the traffic comes from and goes to
            echo and should be 10.X.1.N for X=enclave and 2 \<= N \<= 255.
            echo The gateway for each enclave is assumed to be 10.X.1.1. 
            echo
            echo Defaults are
            echo -e "\tsource_addr: ${TRAF_SRCADDR}"
            echo -e "\tdest_addr: ${TRAF_DSTADDR}"
            echo -e "\tdest_addr: ${TRAF_DSTADDR}"
            echo -e "\tIP protocol: ${TRAF_IPPROTO}"
            echo -e "\tFrame Length ${TRAF_FRAMELEN}"
            echo -e "\tFrames/sec: ${TRAF_FRAMEPERSEC}"
            echo -e "\tTraffic time: ${TRAF_TIME}"
            echo 
            exit 1
            ;;
    esac
done

GW1=$(echo ${TRAF_SRCADDR} | cut -d. -f1-3).1
GW2=$(echo ${TRAF_DSTADDR} | cut -d. -f1-3).1
PORT1=$(echo ${TRAF_SRCADDR} | cut -d. -f2)
PORT2=$(echo ${TRAF_DSTADDR} | cut -d. -f2)
PLOC1="5/${PORT1}"
PLOC2="5/${PORT2}"

SESSHEAD="X-STC-API-Session: ${SESSID} - ${USERID}"
CURLARGS="-s -w '\n'"

HANDLES=

function info() {
    echo INFO: "$*"
    curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d message=\""$*"\" -d loglevel=INFO \
        http://${STCSERV}/stcapi/log &> /dev/null
}

function cleanup() {
    PORTS=
    for p in ${HANDLES}; do
        if [[ ${p} = port* ]]; then
            PORTS=" ${p} ${PORTS}"
        fi
    done
    if [[ ! -z ${PORTS} ]]; then 
        info Detaching from ports ${PORTS}
        curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d command=DetachPorts -d portList="${PORTS}" \
            http://${STCSERV}/stcapi/perform
    else
        info No ports to detatch from, which is weird.
    fi
    info Cleaning up handles: "${HANDLES}"
    for HANDLE in ${HANDLES}; do
        info deleting ${HANDLE}
        curl ${CURLARGS} -X DELETE -H "${SESSHEAD}" "http://${STCSERV}/stcapi/objects/${HANDLE}"
    done
    info closing session "${SESSID} - ${USERID}"
    curl ${CURLARGS} -X DELETE "http://${STCSERV}/stcapi/sessions/${SESSID}%20-%20${USERID}"
}

trap cleanup EXIT

info creating session 
curl ${CURLARGS} -X POST -d userid="${USERID}" -d sessionname="${SESSID}" http://${STCSERV}/stcapi/sessions

info creating project 
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d object_type=project http://${STCSERV}/stcapi/objects
HANDLES=" project1 ${HANDLES}"

info create ports
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d object_type=port -d under=project1 -d name=${PORTRX} \
    -d location="${CHASSIS}/${PLOC1}" http://${STCSERV}/stcapi/objects
HANDLES=" port1 ${HANDLES}"

curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d object_type=port -d under=project1 -d name=${PORTRX} \
    -d location="${CHASSIS}/${PLOC2}" http://${STCSERV}/stcapi/objects
HANDLES=" port2 ${HANDLES}"

# info creating copper
# curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d object_type=EthernetCopper -d under=port1 -d LineSpeed=SPEED_10M \
#     -d Duplex=half -d AutoNegotiation=False http://${STCSERV}/stcapi/objects
# HANDLES=" ethernetcopper1 ${HANDLES}"
# 
# curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d object_type=EthernetCopper -d under=port2 -d LineSpeed=SPEED_10M \
#     -d Duplex=half -d AutoNegotiation=False http://${STCSERV}/stcapi/objects
# HANDLES=" ethernetcopper2 ${HANDLES}"

info attaching to ports.
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d command=attachPorts -d portList="port1 port2" -d autoConnect=True \
    http://${STCSERV}/stcapi/perform

info creating streamblock
# prog guide says this can be a string, but objet reference claims it must be xml (!!!). Ugh.
# FRAMECONF='<frame><config><pdus> <pdu name="eth1" pdu="ethernet:EthernetII\" /> <pdu name="ip_1" pdu="ipv4:IPv4" /> </pdus></config></frame>'
# FRAMECONF="Ethernet Vlan IP"
# prog guide says you can configure the frame in the call to create the streamblock. obj ref says not. server says not.
# FRAME="VLan.1.id 2 IPv4.1.sourceAddr ${TRAF_SRCADDR} IPv4.1.destAddr ${TRAF_DSTADDR}"
# curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d object_type=StreamBlock -d under=port1 -d InsertSig=True -d frameConfig="${FRAMECONF}" -d FrameLengthMode=Fixed -d MaxFrameLength=1200 \
#                                          -d FixedFrameLength=128 -d Load=10 -d LoadUnit=FRAMES_PER_SECOND http://${STCSERV}/stcapi/objects
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d object_type=StreamBlock -d under=port1 -d InsertSig=True \
    -d frameConfig="" -d FrameLengthMode=Fixed -d MaxFrameLength=1200 \
    -d FixedFrameLength=${TRAF_FRAMELEN} -d Load=${TRAF_FRAMEPERSEC} -d LoadUnit=FRAMES_PER_SECOND \
    http://${STCSERV}/stcapi/objects
HANDLES="streamblock1 ${HANDLES}"

# info Creating ethII and ipv4 and VLAN PDUs
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d "object_type=Ethernet:EthernetII" -d under=streamblock1 \
    http://${STCSERV}/stcapi/objects
HANDLES=" ethernet:ethernetii1 ${HANDLES}"

# GTL this fails. The system does not know what a vlans:vlan is even though it's in the documentation - the object reference doc page 4,936.
# GTL prog gruide claims you can add VLAN headers, but no.
# GTL       "The PGA package also supports the definition of VLAN sub-interfaces for Ethernet ports." page 177 programmer's guide.
# The Prog guide claims you can add a VLAN PDU, but uses the "frame" and "frameConfig" argument to create streamblock which doesn't work 
#        and has contradictory documentation anyway! Fuck This Shit.
# GTL - Paul has set the routers to put untagged vlans into vlan 2, so this may not be needed anymore.
#curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d "object_type=vlans:vlan" -d name="vlans_name" -d under=streamblock1 http://${STCSERV}/stcapi/objects
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d "object_type=ipv4:IPv4" -d Gateway=${GW1} -d Protocol=${TRAF_IPPROTO} \
    -d SourceAddr=${TRAF_SRCADDR} -d DestAddr=${TRAF_DSTADDR} -d under=streamblock1  \
    http://${STCSERV}/stcapi/objects
HANDLES=" ipv4:ipv41 ${HANDLES}"

info Applying updates. 
curl ${CURLARGS} -X PUT -H "${SESSHEAD}" http://${STCSERV}/stcapi/apply

info streamblock data:
curl ${CURLARGS} -X GET -H "${SESSHEAD}" http://${STCSERV}/stcapi/objects/streamblock1

info ipv41 data:
curl ${CURLARGS} -X GET -H "${SESSHEAD}" "http://${STCSERV}/stcapi/objects/ipv4:ipv41"
info ipv42 data:
curl ${CURLARGS} -X GET -H "${SESSHEAD}" "http://${STCSERV}/stcapi/objects/ipv4:ipv42"


# Now try sending traffic.
info xxxxxxxxxxxxxxxxxxx port1 children:
curl ${CURLARGS} -X GET -H "${SESSHEAD}" -d children http://${STCSERV}/stcapi/objects/port1

info xxxxxxxxxxxxxxxxxxx porttx generator children:
curl ${CURLARGS} -X GET -H "${SESSHEAD}" -d children http://${STCSERV}/stcapi/objects/port1.generator

info xxxxxxxxxxxxxxxxxxx porttx analyzer children:
curl ${CURLARGS} -X GET -H "${SESSHEAD}" -d children http://${STCSERV}/stcapi/objects/port1.analyzer

info stop generator to be in known state
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d command=GeneratorStop -d generatorlist="generator1" \
    http://${STCSERV}/stcapi/perform

# Is this needed? no idea. "Can't hurt..."
sleep 1

info do ARP to get gateway mac address
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d command=ArpNDStart -d handlelist=streamblock1 \
    -d WaitForArpToFinish=true http://${STCSERV}/stcapi/perform

info verifying arp resolved.
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d command=ArpNDVerifyResolved -d handlelist=streamblock1 \
    http://${STCSERV}/stcapi/perform

info start traffic generator and analyzer
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d command=AnalyzerStart -d analyzerlist="analyzer1" \
    http://${STCSERV}/stcapi/perform
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d command=GeneratorStart -d generatorlist="generator1" \
    http://${STCSERV}/stcapi/perform

info wait ${TRAF_TIME} seconds
sleep ${TRAF_TIME}

info stop generator
curl ${CURLARGS} -X POST -H "${SESSHEAD}" -d command=GeneratorStop -d generatorlist="generator1" \
    http://${STCSERV}/stcapi/perform

exit 0
