FROM python:3.12.8-slim
# [측정 도구] E1~E12 공용 클라이언트(+ 엣지 비교·PLC 계약 시험의 Modbus, 새 베이스 제어 시험의 업무 DB)
RUN pip install --no-cache-dir paho-mqtt==2.1.0 confluent-kafka==2.6.1 pymodbus==3.8.6 "psycopg[binary]==3.2.3"
WORKDIR /repo
