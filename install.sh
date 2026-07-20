#!/usr/bin/env bash
# One-line installer for zotero-cli (Linux/macOS).
#   curl -fsSL https://raw.githubusercontent.com/fchicout/zotero-cli/main/install.sh | bash
#
# Downloads the latest pre-compiled amd64 binary from GitHub Releases and
# installs it to ~/.local/bin. No Python installation required.
set -euo pipefail

REPO="fchicout/zotero-cli"
INSTALL_DIR="${ZOTERO_CLI_INSTALL_DIR:-$HOME/.local/bin}"

os="$(uname -s)"
arch="$(uname -m)"

case "$os" in
    Linux|Darwin) ;;
    *)
        echo "Error: unsupported OS '$os'. This script supports Linux and macOS only." >&2
        echo "Windows users: see install.ps1 instead." >&2
        exit 1
        ;;
esac

case "$arch" in
    x86_64|amd64) ;;
    *)
        echo "Error: unsupported architecture '$arch'. Only amd64/x86_64 release binaries are published today." >&2
        exit 1
        ;;
esac

asset="zotero-cli-linux-amd64.tar.gz"
url="https://github.com/${REPO}/releases/latest/download/${asset}"

echo "Downloading ${asset} from the latest release..."
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

curl -fsSL "$url" -o "${tmp_dir}/${asset}"
tar -xzf "${tmp_dir}/${asset}" -C "$tmp_dir"

mkdir -p "$INSTALL_DIR"
mv "${tmp_dir}/zotero-cli" "${INSTALL_DIR}/zotero-cli"
chmod +x "${INSTALL_DIR}/zotero-cli"

echo "Installed zotero-cli to ${INSTALL_DIR}/zotero-cli"
if ! command -v zotero-cli >/dev/null 2>&1; then
    echo "Note: ${INSTALL_DIR} is not on your PATH. Add it, e.g.:"
    echo "  export PATH=\"${INSTALL_DIR}:\$PATH\""
fi
