FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV LOG_LEVEL=INFO

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        ca-certificates \
        curl \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
COPY bridge_server.py /app/bridge_server.py
COPY scraper_client.py /app/scraper_client.py
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

EXPOSE 8099
CMD ["/app/run.sh"]
