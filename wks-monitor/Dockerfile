FROM python:3.12-alpine
WORKDIR /
COPY . .
RUN pip install --no-cache-dir paho-mqtt pyserial
CMD ["sh", "/run.sh"]

