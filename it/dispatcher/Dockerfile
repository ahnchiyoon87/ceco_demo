# IT 발송기(자체 코드). 빌드 컨텍스트 = 저장소 루트
FROM python:3.12-slim
RUN pip install --no-cache-dir "psycopg[binary]==3.2.3" confluent-kafka==2.6.1
COPY it/dispatcher/dispatcher.py /opt/ar100/dispatcher.py
USER nobody
CMD ["python", "-u", "/opt/ar100/dispatcher.py"]
