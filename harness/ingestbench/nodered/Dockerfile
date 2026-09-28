# 수집 후보 P2: Node-RED 5.0.7 + node-red-contrib-modbus 5.60.2 (CANDIDATES §2)
# 흐름(flows.json)은 이미지에 굽는다(/data 는 이미지 VOLUME 이라 첫 생성 시 복사됨).
FROM nodered/node-red:5.0.7
RUN npm install --no-audit --no-fund --omit=dev node-red-contrib-modbus@5.60.2
COPY --chown=node-red:node-red flows.json /data/flows.json
