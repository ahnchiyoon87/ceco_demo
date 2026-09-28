FROM python:3.12.8-slim
RUN pip install --no-cache-dir confluent-kafka==2.6.1
WORKDIR /app
COPY app.py .
CMD ["python", "-u", "app.py"]
