# based bot - Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libdbus-1-3 \
        libxkbcommon0 \
        libatspi2.0-0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-bot.txt requirements-skeds.txt pyproject.toml ./

RUN pip install --upgrade pip \
 && pip install -r requirements.txt \
 && pip install -r requirements-bot.txt \
 && pip install -r requirements-skeds.txt \
 && pip install markdown playwright \
 && pip install faster-whisper ctranslate2 \
 && playwright install chromium

COPY based ./based
COPY bot ./bot
COPY samples ./samples
COPY verify.py ./

RUN pip install -e .

ENV BASED_CACHE_DIR=/data/based \
    BOT_CACHE_DIR=/data/bot

RUN mkdir -p /data/based /data/bot

EXPOSE 8080

CMD ["python", "-m", "bot"]
