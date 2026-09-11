FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OPERACIONAL_ROOT=/data/operacional \
    APP_HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app
COPY requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY run.py ./
COPY railway-entrypoint.sh ./
RUN useradd --system --uid 10001 --create-home operacional \
    && mkdir -p /data/operacional/data /data/operacional/logs \
    && chown -R operacional:operacional /data/operacional \
    && chmod +x railway-entrypoint.sh
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"
ENTRYPOINT ["./railway-entrypoint.sh"]
