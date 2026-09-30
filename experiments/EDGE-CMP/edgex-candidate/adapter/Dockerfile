# EdgeX 엣지 후보의 UNS 어댑터·OT 작업 요청 수신기(자체 코드). 빌드 컨텍스트 = 저장소 루트
FROM python:3.12-slim
RUN pip install --no-cache-dir paho-mqtt==2.1.0 jsonschema==4.23.0
COPY experiments/EDGE-CMP/edgex-candidate/adapter/adapter.py /opt/ar100/adapter.py
COPY registry/generated/ /opt/ar100/registry/
USER nobody
CMD ["python", "-u", "/opt/ar100/adapter.py"]
