#!/usr/bin/env bash
# One-line installer for zotero-cli (Linux, amd64).
#   curl -fsSL https://raw.githubusercontent.com/fchicout/zotero-cli/main/install.sh | bash
#
# Downloads a pre-compiled binary from GitHub Releases, verifies it against
# the release's SHA256SUMS, and installs it to ~/.local/bin. No Python
# installation required.
#
# Environment variables:
#   ZOTERO_CLI_VERSION      release to install, e.g. v3.0.0 (default: latest)
#   ZOTERO_CLI_INSTALL_DIR  install directory (default: ~/.local/bin)
#
# Everything runs inside main(), called on the last line, so a download cut
# short midway through `curl | bash` runs nothing at all.
set -euo pipefail

main() {
    local repo="fchicout/zotero-cli"
    local install_dir="${ZOTERO_CLI_INSTALL_DIR:-$HOME/.local/bin}"
    local version="${ZOTERO_CLI_VERSION:-latest}"
    local asset="zotero-cli-linux-amd64.tar.gz"

    local os arch
    os="$(uname -s)"
    arch="$(uname -m)"

    # Where there is no binary, the Python package is the supported route
    # (Issue #404): uv/pipx install it as an isolated command.
    local python_route="uv tool install zotero-command-line   (or: pipx install zotero-command-line)"

    if [ "$os" = "Darwin" ]; then
        echo "No macOS binary is published. On macOS, install the Python package:" >&2
        echo "  $python_route" >&2
        echo "(uv: https://docs.astral.sh/uv/ - needs Python 3.11+, which uv can install for you)" >&2
        exit 1
    fi
    if [ "$os" != "Linux" ]; then
        echo "Error: unsupported OS '$os'. Release binaries exist for Linux and Windows only." >&2
        echo "Windows users: see install.ps1. Elsewhere: $python_route" >&2
        exit 1
    fi
    case "$arch" in
        x86_64|amd64) ;;
        *)
            echo "Error: unsupported architecture '$arch'. Only amd64/x86_64 binaries are published." >&2
            echo "Install the Python package instead: $python_route" >&2
            exit 1
            ;;
    esac
    # The binary needs glibc 2.35+ (Ubuntu 22.04, Debian 12, Fedora 36 or
    # newer). musl (Alpine) and older glibc: use the Python package.
    local glibc
    glibc="$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')"
    if [ -z "$glibc" ]; then
        echo "Error: this system doesn't use glibc (e.g. Alpine), which the binary needs." >&2
        echo "Install the Python package instead: $python_route" >&2
        exit 1
    fi
    if [ "$(printf '%s\n' 2.35 "$glibc" | sort -V | head -n1)" != "2.35" ]; then
        echo "Error: glibc $glibc is too old for the binary (needs 2.35 or newer)." >&2
        echo "Install the Python package instead: $python_route" >&2
        exit 1
    fi
    if ! command -v sha256sum > /dev/null 2>&1; then
        echo "Error: sha256sum is required to verify the download." >&2
        exit 1
    fi

    local base_url
    if [ "$version" = "latest" ]; then
        base_url="https://github.com/${repo}/releases/latest/download"
    else
        base_url="https://github.com/${repo}/releases/download/${version}"
    fi

    local tmp_dir
    tmp_dir="$(mktemp -d)"
    # shellcheck disable=SC2064  # expand tmp_dir now, while it's in scope
    trap "rm -rf '$tmp_dir'" EXIT

    echo "Downloading ${asset} (${version})..."
    curl -fsSL "${base_url}/${asset}" -o "${tmp_dir}/${asset}"
    if ! curl -fsSL "${base_url}/SHA256SUMS" -o "${tmp_dir}/SHA256SUMS"; then
        echo "Error: this release has no SHA256SUMS (checksums are published from v2.8.12 on)." >&2
        echo "Refusing to install an unverified binary." >&2
        exit 1
    fi

    echo "Verifying checksum..."
    (cd "$tmp_dir" && grep " ${asset}\$" SHA256SUMS | sha256sum -c --strict -) || {
        echo "Error: checksum verification failed for ${asset}. Not installing." >&2
        exit 1
    }

    tar -xzf "${tmp_dir}/${asset}" -C "$tmp_dir"
    mkdir -p "$install_dir"
    install -m 0755 "${tmp_dir}/zotero-cli" "${install_dir}/zotero-cli"

    echo "Installed zotero-cli to ${install_dir}/zotero-cli"
    if ! command -v zotero-cli > /dev/null 2>&1; then
        echo "Note: ${install_dir} is not on your PATH. Add it, e.g.:"
        echo "  export PATH=\"${install_dir}:\$PATH\""
    fi
}

main "$@"
