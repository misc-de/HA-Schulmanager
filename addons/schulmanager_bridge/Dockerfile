FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV LOG_LEVEL=INFO

# The bridge talks to the Schulmanager JSON API over HTTPS; no browser needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
COPY bridge_server.py /app/bridge_server.py
COPY api_client.py /app/api_client.py
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

EXPOSE 8099
CMD ["/app/run.sh"]
