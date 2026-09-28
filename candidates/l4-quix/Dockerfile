# L4 후보 Quix Streams 3.26.0 (CANDIDATES §1 [묶음 K-lib] P1). 엔진 = quixstreams 라이브러리(Apache-2.0).
FROM python:3.12.8-slim
RUN pip install --no-cache-dir quixstreams==3.26.0 onnxruntime==1.20.1 numpy==2.1.3   # onnxruntime: V1 과 같은 1.20 계열(tools 이미지와 같은 판)
WORKDIR /app
COPY app.py .
CMD ["python", "-u", "app.py"]
