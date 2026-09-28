FROM python:3.12.8-slim
RUN pip install --no-cache-dir confluent-kafka==2.6.1 onnxruntime==1.20.1 numpy==2.1.3 prometheus-client==0.21.1
WORKDIR /app
COPY app.py ml.py ./
CMD ["python", "-u", "app.py"]
