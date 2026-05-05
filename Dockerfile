FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DB_PATH=/data/app.db

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app

RUN pip install --upgrade pip uv && uv sync

RUN useradd --system --home /app --shell /usr/sbin/nologin ipay \
 && mkdir -p /data && chown -R ipay:ipay /data /app

USER ipay
VOLUME ["/data"]
EXPOSE 80

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers"]
