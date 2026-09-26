# 📖 Tutorial: Configuring `zotero-cli`

To use this tool, you need to link it to your Zotero account by filling out the `config.toml` file. Follow these steps to find your credentials and optional service keys.

## 1. Get Your Zotero API Key
The API Key is a secret token that allows the CLI to access your library.

1.  **Log in** to your account at [zotero.org](https://www.zotero.org/).
2.  Navigate directly to your **Security Settings**: [zotero.org/settings/security](https://www.zotero.org/settings/security).
3.  Scroll down to the **Applications** section of the page.
4.  Click the **"Create new private key"** button.
5.  **Configure your key:**
    *   **Description:** Give it a name (e.g., `zotero-cli-work`).
    *   **Library Access:** Ensure "Allow library access" is checked.
    *   **Write Access:** Check "Allow write access" if you want the CLI to add, move, or edit items.
6.  Click **Save Key** and copy the long string immediately (it won't be shown again). This is your `api_key`.

## 2. Find Your Personal User ID
This unique number is required for the tool to identify your account and discover your groups.

1.  On the same **Security Settings** page ([zotero.org/settings/security](https://www.zotero.org/settings/security)), scroll to the **Applications** section.
2.  Look **right below** the "Create new private key" button. 
3.  You will see: **"Your userID for API calls is XXXXXX"**. This is your `user_id`.

## 3. Manage Your Library ID (`library_id`)
The `library_id` tells the tool which library to target by default.

*   **Switching groups via CLI:** Use `zotero-cli system switch 1234567` (a group ID, or part of the group's name) to change the active group without editing the file manually. `zotero-cli system groups` lists the groups your key can access.
*   **The --user Flag:** Adding the global `--user` flag to a command (for example `zotero-cli --user item list`) targets your personal library for that command only. It doesn't change the configured library or enable offline mode; offline mode is the separate `--offline` flag.

> **⚠️ Offline Mode scope:** `--offline` reads directly from your local `zotero.sqlite` file and does **not** filter by `library_id`/`library_type` - it operates across the *entire* local database. If Zotero Desktop syncs more than one library on this machine (your personal library plus any groups), offline-mode commands will see and count items from all of them, not just the one configured in `config.toml`. This can produce item counts, PRISMA totals, or screening results that don't match what the same commands report in online mode. If you only ever sync one library locally, this doesn't affect you.
>
> `--offline` is also **read-only**: most write-oriented commands (`slr decide`, `slr screen`, `item update`, `slr snowball import`, etc.) aren't offline-compatible and will fail with "Offline mode is read-only" if you forget to drop the flag. `item trash`/`item restore` are the only write paths offline mode explicitly supports.

## 4. Boost Your Research (Optional Services)
Adding these parameters to `config.toml` unlocks powerful automation features:

### 🚀 Semantic Scholar API Key
Provides high-speed metadata hydration and citation analysis.
*   **How to get it:** Request a free API key at [semanticscholar.org/product/api#api-key-form](https://www.semanticscholar.org/product/api#api-key-form).
*   **Benefit:** Faster item hydration and improved discovery of related research.

### 🔓 Unpaywall Email
A database of over 50 million free, open-access scholarly articles. 
*   **How to set it:** Simply add your email address to the `unpaywall_email` field.
*   **Benefit:** High-success PDF discovery. The tool uses this email to search Unpaywall and automatically attach legal PDFs to your Zotero items.
*   **Also your contact address for other services:** CrossRef, OpenAlex and NCBI/PubMed ask API clients to identify a contact so they can reach you before throttling heavy use (their "polite pool"). zotero-cli sends this email to them when it's set, and no email at all when it isn't. Unpaywall itself requires an email, so without one it's skipped.

---

## Example `config.toml` Summary
```toml
[zotero]
api_key = "YOUR_ZOTERO_API_KEY"
user_id = "YOUR_USER_ID"
library_id = "YOUR_GROUP_ID"
library_type = "group"

# Optional Extensions
semantic_scholar_api_key = "YOUR_KEY_HERE"
unpaywall_email = "your.email@example.com"
```

**File Locations:**
*   **Linux/macOS:** `~/.config/zotero-cli/config.toml`
*   **Windows:** `%APPDATA%\zotero-cli\config.toml`

## Where zotero-cli keeps its files

Everything lives in one directory, which zotero-cli makes private to your user account (mode `0700`):

- **Linux/macOS:** `~/.config/zotero-cli/` (or `$XDG_CONFIG_HOME/zotero-cli/`)
- **Windows:** `%APPDATA%\zotero-cli\`

It holds `config.toml` (your keys, mode `0600`), the background job queue (`jobs.sqlite`), snowball discovery graphs, `rag` vector stores, and the log files in `logs/`. `logs/zotero-cli.log` records INFO and above on every run, rotated at 5 MB with 3 old files kept. Log files are created `0600`.

**With `--config PATH`:** the config file stays where you put it, but zotero-cli's state (job queue, graphs, vector stores) goes into a private profile inside the directory above, `profiles/<id>/`, one per config file, never next to the config file. Logs always go to `logs/` there. Versions before 3.1 wrote that state next to the `--config` file, world-readable; zotero-cli moves it into the profile the first time it runs and says so. `zotero-cli system info` shows the state and log directories in use. A `resolvers.yaml` with custom PDF resolvers is still read from the config file's directory.

zotero-cli masks API keys, tokens and credential URL parameters before writing any log line, in the file and on screen. Still, check a log for anything private before attaching it to an issue, and never post your `config.toml`.
