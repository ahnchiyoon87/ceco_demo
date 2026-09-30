# DMZ 요청 게이트웨이(자체 코드). 빌드 컨텍스트 = 저장소 루트
FROM python:3.12-slim
RUN pip install --no-cache-dir aiohttp==3.11.11 paho-mqtt==2.1.0 jsonschema==4.23.0
COPY 3_dmz/gateway/gateway.py /opt/ar100/gateway.py
COPY shared/registry/generated/ /opt/ar100/registry/
USER nobody
EXPOSE 8088
CMD ["python", "-u", "/opt/ar100/gateway.py"]
