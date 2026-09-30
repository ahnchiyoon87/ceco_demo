#!/bin/sh
# 생성된 흐름을 배포하고 Node-RED 를 띄운다. 편집기에서 바꾼 흐름은 다음 기동 때 정본(등록부 생성본)으로 돌아간다.
set -eu
cp /opt/ar100/flows.json /opt/ar100/flows_cred.json /data/
exec node /usr/src/node-red/node_modules/node-red/red.js --userDir /data --settings /opt/ar100/settings.js
