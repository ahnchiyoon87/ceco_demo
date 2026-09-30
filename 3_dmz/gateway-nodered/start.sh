#!/bin/sh
# 생성된 흐름을 배포하고 Node-RED 를 띄운다.
set -eu
mkdir -p /data
cp /opt/ar100/flows.json /opt/ar100/flows_cred.json /data/
exec node /usr/src/node-red/node_modules/node-red/red.js --userDir /data --settings /opt/ar100/settings.js
