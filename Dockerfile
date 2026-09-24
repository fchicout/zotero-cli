# Lightweight runtime image: builds the same self-contained PyInstaller
# binary as .github/workflows/release.yml (same --exclude-module flags, so
# the image doesn't ship torch/numpy/etc.), then copies just the binary
# into a slim base with no Python interpreter needed at runtime.
#
# Issue #338: the base image is pinned by digest in both stages (Dependabot
# keeps it current), dependencies come from uv.lock, and the container runs as an
# unprivileged user.
FROM python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9 AS builder

WORKDIR /build
COPY . .

# binutils provides objdump, which PyInstaller requires on Linux to analyze
# shared library dependencies - present on GitHub Actions' ubuntu-22.04
# runner by default, but not on this slim base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends binutils \
    && rm -rf /var/lib/apt/lists/*

# Exactly what uv.lock pins (Issue #333), plus the locked `release` group
# (PyInstaller). An unlocked `uv pip install .` could resolve different,
# even incompatible, versions.
RUN pip install --no-cache-dir "uv==0.12.18" && \
    uv sync --locked --no-editable --group release

RUN .venv/bin/pyinstaller --onefile --name zotero-cli \
    --add-data "src/zotero_cli/templates/extraction_schema.yaml:zotero_cli/templates" \
    --add-data "src/zotero_cli/templates/demo_sandbox.yaml:zotero_cli/templates" \
    --exclude-module torch \
    --exclude-module nvidia \
    --exclude-module mkl \
    --exclude-module numpy \
    --exclude-module pandas \
    --exclude-module matplotlib \
    --clean src/zotero_cli/cli/main.py

FROM python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9 AS runtime

# Reuses the same base as the builder stage rather than a separately-tagged
# distro (e.g. debian:bookworm-slim) - a mismatched glibc between build and
# runtime breaks the PyInstaller binary at startup (verified: "GLIBC_2.38
# not found" when the runtime base was one Debian release behind the
# builder's). Only the compiled binary is actually used from this image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin zotero \
    && install -d -m 0755 /config \
    && install -d -o zotero -g zotero -m 0700 /config/zotero-cli

COPY --from=builder /build/dist/zotero-cli /usr/local/bin/zotero-cli

# Config, logs and job state live in /config/zotero-cli, outside any home
# directory, so a bind mount there works for whichever user runs the
# container. Runs unprivileged: root in the container would leave
# root-owned files in a mounted directory. To own what it writes, run with
# `--user "$(id -u):$(id -g)"` and mount your config directory - or pass
# settings as environment variables with --env-file. See README.md.
ENV XDG_CONFIG_HOME=/config
USER zotero
WORKDIR /home/zotero
ENTRYPOINT ["zotero-cli"]
CMD ["--help"]
