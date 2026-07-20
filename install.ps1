# One-line installer for zotero-cli (Windows).
#   irm https://raw.githubusercontent.com/fchicout/zotero-cli/main/install.ps1 | iex
#
# Downloads the latest pre-compiled amd64 binary from GitHub Releases and
# installs it to %LOCALAPPDATA%\zotero-cli. No Python installation required.

$ErrorActionPreference = "Stop"

$Repo = "fchicout/zotero-cli"
$InstallDir = if ($env:ZOTERO_CLI_INSTALL_DIR) { $env:ZOTERO_CLI_INSTALL_DIR } else { "$env:LOCALAPPDATA\zotero-cli" }
$Asset = "zotero-cli-windows-amd64.zip"
$Url = "https://github.com/$Repo/releases/latest/download/$Asset"

Write-Host "Downloading $Asset from the latest release..."

$TempDir = New-Item -ItemType Directory -Path (Join-Path $env:TEMP ([System.Guid]::NewGuid()))
$ZipPath = Join-Path $TempDir $Asset

try {
    Invoke-WebRequest -Uri $Url -OutFile $ZipPath
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
