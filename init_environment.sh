#!/usr/bin/env bash

VDIR=venv

if [[ -e ${VDIR} ]]; then
    echo Environment already initialized. Destroying and recreating it. 
    rm -rf ${VDIR}
fi

virtualenv -p python3 ${VDIR}
. ./${VDIR}/bin/activate
pip install -U stcrestclient
