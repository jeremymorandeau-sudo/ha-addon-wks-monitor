ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}
WORKDIR /app
COPY . /app/
RUN apk add --no-cache python3 py3-pip &&         pip install --break-system-packages --no-cache-dir pyserial paho-mqtt
ENTRYPOINT ["python3", "/app/wks_monitor.py"]
