FROM python:3.13-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY api.py /app/api.py
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/entrypoint.py /app/entrypoint.py
COPY site /app/site

ENV PYTHONUNBUFFERED=1
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1/api/health')"

CMD ["python", "/app/entrypoint.py"]
