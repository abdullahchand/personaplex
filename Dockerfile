# Persona (Moshi) voice server; optional handoff POSTs full-conversation WAV to agent-service for remote STT
ARG BASE_IMAGE="nvcr.io/nvidia/cuda"
ARG BASE_IMAGE_TAG="12.4.1-runtime-ubuntu22.04"

FROM ${BASE_IMAGE}:${BASE_IMAGE_TAG} AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libopus-dev \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/moshi/

# uv defaults to reflinks/hardlinks that often fail on Docker/WSL overlay (EAGAIN on large wheels).
ENV UV_LINK_MODE=copy \
    UV_CONCURRENT_INSTALLS=1 \
    UV_CONCURRENT_DOWNLOADS=4

COPY moshi/ /app/moshi/
RUN uv venv /app/moshi/.venv --python 3.12
RUN uv sync --link-mode copy

RUN mkdir -p /app/ssl

EXPOSE 8998

ENTRYPOINT []
CMD ["/app/moshi/.venv/bin/python", "-m", "moshi.server", "--ssl", "/app/ssl"]
