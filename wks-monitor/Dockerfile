ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}

# Configuration locale du conteneur
WORKDIR /app

# Copie du script principal
COPY wks_monitor.py /app/

# Installation des dépendances Python
RUN apk add --no-cache python3 py3-pip && \
    pip install --break-system-packages --no-cache-dir pyserial paho-mqtt

# --- Démarrage direct du script sans shell intermédiaire ---
ENTRYPOINT ["python3", "/app/wks_monitor.py"]
