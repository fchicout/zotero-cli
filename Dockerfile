# Lightweight runtime image: builds the same self-contained PyInstaller
# binary as .github/workflows/release.yml (same --exclude-module flags, so
# the image doesn't ship torch/numpy/etc.), then copies just the binary
# into a slim base with no Python interpreter needed at runtime.

FROM python:3.11-slim AS builder

WORKDIR /build
COPY . .

# binutils provides objdump, which PyInstaller requires on Linux to analyze
# shared library dependencies - present on GitHub Actions' ubuntu-22.04
# runner by default, but not on this slim base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends binutils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv && \
    uv pip install --system . && \
    uv pip install --system pyinstaller

RUN pyinstaller --onefile --name zotero-cli \
    --add-data "src/zotero_cli/templates/extraction_schema.yaml:zotero_cli/templates" \
    --add-data "src/zotero_cli/templates/demo_sandbox.yaml:zotero_cli/templates" \
    --exclude-module torch \
    --exclude-module nvidia \
    --exclude-module mkl \
    --exclude-module numpy \
    --exclude-module pandas \
    --exclude-module matplotlib \
    --clean src/zotero_cli/cli/main.py

FROM python:3.11-slim AS runtime

# Reuses the same base as the builder stage rather than a separately-tagged
# distro (e.g. debian:bookworm-slim) - a mismatched glibc between build and
# runtime breaks the PyInstaller binary at startup (verified: "GLIBC_2.38
# not found" when the runtime base was one Debian release behind the
# builder's). Only the compiled binary is actually used from this image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/dist/zotero-cli /usr/local/bin/zotero-cli

# Configure via env vars (ZOTERO_API_KEY, ZOTERO_LIBRARY_ID, ZOTERO_USER_ID, ...)
# or by mounting ~/.config/zotero-cli/config.toml - see README.md.
ENTRYPOINT ["zotero-cli"]
CMD ["--help"]
