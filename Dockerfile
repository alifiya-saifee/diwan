# Diwan on a Linux host. One instance only, with a persistent disk mounted at /data (deploy/start.py).
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN grep -v -E '^(pytest|faster-whisper)' requirements.txt > runtime.txt \
    && pip install --no-cache-dir -r runtime.txt

# Named folders only, so .env, the databases and media can never end up in the image.
COPY diwan ./diwan
COPY web ./web
COPY tapes ./tapes
COPY evals ./evals
COPY deploy ./deploy

# The spend ledger sits on the disk, or the monthly cap would reset on every deploy.
RUN ln -s /data/usage.jsonl /app/usage.jsonl

ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1
CMD ["python", "-m", "deploy.start"]
