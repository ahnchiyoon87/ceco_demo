FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY plant.py sim.py plant.yaml ./
ENV PLANT_CONFIG=/app/plant.yaml MODBUS_PORT=502 API_PORT=8080
EXPOSE 502 8080
CMD ["python", "-u", "sim.py"]
