# Full development environment (unlike the root Dockerfile, size isn't a
# concern here - this installs the complete dependency set, including
# the dev extras, for GitHub Codespaces / VS Code Dev Containers).
FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /workspace
