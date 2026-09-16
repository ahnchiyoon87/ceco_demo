# 빌드 컨텍스트는 프로젝트 루트입니다 (compose 의 context: .).
# 물리 모델을 복사본이 아니라 simulator/ 원본에서 직접 가져와
# 학습 분포와 운영 분포가 어긋나지 않게 합니다.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.8.0 \
 && pip install --no-cache-dir numpy==2.1.3 PyYAML==6.0.2 onnx==1.17.0 onnxruntime==1.20.1
COPY ml/train.py ml/train.yaml ./
COPY simulator/plant.py simulator/plant.yaml ./
ENV TRAIN_CONFIG=/app/train.yaml
CMD ["python", "-u", "train.py"]
