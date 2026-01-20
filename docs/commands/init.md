# Command: `init`

**Namespace:** Global
**Purpose:** Setup and configure `zotero-cli` through an interactive wizard.

---

## Overview

The `init` command allows you to easily configure your Zotero API credentials and other third-party service settings. It generates a `config.toml` file in your default configuration directory (or at a custom path if specified).

## Usage

```bash
zotero-cli init [OPTIONS]
```

### Options

*   `--force`: Overwrite the existing configuration file if it already exists.
*   `--config <PATH>`: Specify a custom path for the configuration file.

## Interactive Prompts

The wizard will guide you through the following fields:

1.  **Zotero API Key**: Your personal API key. Generate one at [zotero.org/settings/keys](https://www.zotero.org/settings/keys).
2.  **Library Type**: Choose between `user` or `group`.
3.  **Library ID**: The User ID or Group ID of the target library.
4.  **User ID** (Optional): Your personal User ID, used when you want to switch to personal library mode via the `--user` flag.
5.  **Target Group Name** (Optional): The slug name of the group from its URL.
6.  **Semantic Scholar API Key** (Optional): Used for bulk metadata lookup.
7.  **Unpaywall Email** (Optional): Used for finding Open Access PDFs.

## Verification

Before saving, the wizard attempts to verify your Zotero API credentials by making a lightweight request to the Zotero API. If verification fails, you will be warned and asked if you want to proceed anyway.

## Examples

### Basic Setup
```bash
zotero-cli init
```

### Force Overwrite
```bash
zotero-cli init --force
```

### Save to Custom Location
```bash
zotero-cli init --config ./my_project_config.toml
```

## Next Steps

After running `init`, you can verify your configuration with:
```bash
zotero-cli system info
```
