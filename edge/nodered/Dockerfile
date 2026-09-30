# 엣지 후보 1 — Node-RED 5.0.7(Apache-2.0) + node-red-contrib-modbus 5.60.2(BSD-3-Clause)
# 흐름(flows.json)은 설비 등록부에서 생성한다(registry/generate.py). 기동할 때마다 생성본을 배포한다.
FROM nodered/node-red:5.0.7
RUN cd /usr/src/node-red && npm install --no-audit --no-fund --omit=dev node-red-contrib-modbus@5.60.2 \
 && npm cache clean --force
# 빌드 컨텍스트 = 저장소 루트(등록부 생성본을 함께 넣는다)
COPY --chown=node-red:root edge/nodered/settings.js edge/nodered/flows.json edge/nodered/flows_cred.json edge/nodered/start.sh /opt/ar100/
COPY --chown=node-red:root registry/generated/ /opt/ar100/registry/
ENTRYPOINT ["sh", "/opt/ar100/start.sh"]
