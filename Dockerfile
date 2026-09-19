# syntax=docker/dockerfile:1.7
# Obrazy Danaco Nexus: "api" (FastAPI + interfejs WWW) i "worker" (agent + narzędzia).

FROM node:22-bookworm-slim AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-trixie AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NEXUS_DATA_DIR=/data
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin nexus
WORKDIR /app
COPY backend/pyproject.toml ./
RUN mkdir -p nexus && touch nexus/__init__.py && pip install . && pip uninstall -y danaco-nexus
COPY backend/nexus ./nexus

FROM python-base AS api
COPY --from=frontend /src/dist /app/static
USER nexus
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["uvicorn", "nexus.api.app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-graceful-shutdown", "20"]

FROM python-base AS worker
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-pol tesseract-ocr-eng tesseract-ocr-deu tesseract-ocr-osd \
        unpaper imagemagick ffmpeg inkscape \
        libreoffice-writer-nogui libreoffice-calc-nogui libreoffice-impress-nogui \
        mesa-vulkan-drivers libvulkan1 libgomp1 \
        fonts-liberation2 fonts-crosextra-carlito fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*
USER nexus
CMD ["python", "-m", "nexus.worker"]
