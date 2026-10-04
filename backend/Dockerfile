FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System libs for audio/media wheels (PyAV/onnxruntime fallbacks).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY agent ./agent
COPY web ./web

EXPOSE 8000
