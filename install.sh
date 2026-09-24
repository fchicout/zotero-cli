#!/usr/bin/env bash
# One-line installer for zotero-cli (Linux, amd64).
#   curl -fsSL https://raw.githubusercontent.com/fchicout/zotero-cli/main/install.sh | bash
#
# Downloads a pre-compiled binary from GitHub Releases, verifies it against
# the release's SHA256SUMS, and installs it to ~/.local/bin. No Python
# installation required.
#
# Environment variables:
#   ZOTERO_CLI_VERSION      release to install, e.g. v2.8.12 (default: latest)
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

    if [ "$os" != "Linux" ]; then
        echo "Error: unsupported OS '$os'. Release binaries exist for Linux and Windows only." >&2
        echo "Windows users: see install.ps1. Elsewhere: pip install zotero-command-line" >&2
        exit 1
    fi
    case "$arch" in
        x86_64|amd64) ;;
        *)
            echo "Error: unsupported architecture '$arch'. Only amd64/x86_64 binaries are published." >&2
            echo "Alternative: pip install zotero-command-line" >&2
            exit 1
            ;;
    esac
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
