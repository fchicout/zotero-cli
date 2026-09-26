# One-line installer for zotero-cli (Windows, amd64).
#   irm https://raw.githubusercontent.com/fchicout/zotero-cli/main/install.ps1 | iex
#
# Downloads a pre-compiled binary from GitHub Releases, verifies it against
# the release's SHA256SUMS, and installs it to %LOCALAPPDATA%\zotero-cli.
# No Python installation required.
#
# Environment variables:
#   ZOTERO_CLI_VERSION      release to install, e.g. v3.0.0 (default: latest)
#   ZOTERO_CLI_INSTALL_DIR  install directory (default: %LOCALAPPDATA%\zotero-cli)
#
# Everything runs inside Install-ZoteroCli, called on the last line, so a
# download cut short midway through `irm | iex` runs nothing at all.

function Install-ZoteroCli {
    $ErrorActionPreference = "Stop"

    $Repo = "fchicout/zotero-cli"
    $InstallDir = if ($env:ZOTERO_CLI_INSTALL_DIR) { $env:ZOTERO_CLI_INSTALL_DIR } else { "$env:LOCALAPPDATA\zotero-cli" }
    $Version = if ($env:ZOTERO_CLI_VERSION) { $env:ZOTERO_CLI_VERSION } else { "latest" }
    $Asset = "zotero-cli-windows-amd64.zip"
    $BaseUrl = if ($Version -eq "latest") {
        "https://github.com/$Repo/releases/latest/download"
    } else {
        "https://github.com/$Repo/releases/download/$Version"
    }

    $TempDir = New-Item -ItemType Directory -Path (Join-Path $env:TEMP ([System.Guid]::NewGuid()))
    $ZipPath = Join-Path $TempDir $Asset
    $SumsPath = Join-Path $TempDir "SHA256SUMS"

    try {
        Write-Host "Downloading $Asset ($Version)..."
        Invoke-WebRequest -Uri "$BaseUrl/$Asset" -OutFile $ZipPath
        try {
            Invoke-WebRequest -Uri "$BaseUrl/SHA256SUMS" -OutFile $SumsPath
        } catch {
            throw "This release has no SHA256SUMS (checksums are published from v2.8.12 on). Refusing to install an unverified binary."
        }

        Write-Host "Verifying checksum..."
        $Line = Get-Content $SumsPath | Where-Object { $_ -match "\s\*?$([regex]::Escape($Asset))$" } | Select-Object -First 1
        if (-not $Line) { throw "No checksum for $Asset in SHA256SUMS. Not installing." }
        $Expected = ($Line -split '\s+')[0].ToLowerInvariant()
        $Actual = (Get-FileHash -Algorithm SHA256 -Path $ZipPath).Hash.ToLowerInvariant()
        if ($Expected -ne $Actual) { throw "Checksum verification failed for $Asset. Not installing." }

        Expand-Archive -Path $ZipPath -DestinationPath $TempDir -Force
        New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
        Move-Item -Force (Join-Path $TempDir "zotero-cli.exe") (Join-Path $InstallDir "zotero-cli.exe")

        Write-Host "Installed zotero-cli to $InstallDir\zotero-cli.exe"

        $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($UserPath -notlike "*$InstallDir*") {
            Write-Host "Note: $InstallDir is not on your PATH. Add it, e.g.:"
            Write-Host "  [Environment]::SetEnvironmentVariable('Path', `"`$env:Path;$InstallDir`", 'User')"
        }
    } finally {
        Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
    }
}

Install-ZoteroCli
