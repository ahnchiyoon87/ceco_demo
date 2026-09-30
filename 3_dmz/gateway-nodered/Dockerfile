# DMZ 요청 게이트웨이 — Node-RED 5.0.7(Apache-2.0). 흐름은 설비 등록부에서 생성한다(shared/registry/generate.py).
FROM nodered/node-red:5.0.7
# 빌드 컨텍스트 = 저장소 루트(등록부 생성본을 함께 넣는다)
COPY --chown=node-red:root 3_dmz/gateway-nodered/settings.js 3_dmz/gateway-nodered/flows.json 3_dmz/gateway-nodered/flows_cred.json 3_dmz/gateway-nodered/start.sh /opt/ar100/
COPY --chown=node-red:root shared/registry/generated/ /opt/ar100/registry/
EXPOSE 8088
ENTRYPOINT ["sh", "/opt/ar100/start.sh"]
