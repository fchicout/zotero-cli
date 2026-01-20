# Tutorial 1: Getting Started with Zotero CLI

**Audience:** Researchers, Students, and anyone who loves Zotero but is new to the Command Line.
**Goal:** Connect this tool to your Zotero account and run your first command.

---

## 1. What is this tool?
Think of `zotero-cli` as a "Systematic Review Engine" that lives outside of Zotero. It helps you:
*   **Screen papers** faster (using a dedicated interface).
*   **Clean up** your metadata and find duplicates.
*   **Generate PRISMA reports** automatically.

It runs in a window called the **Terminal**, but don't worry—we'll guide you through every step.

## 2. Prerequisites
Before we start, you need two things from the Zotero website:

### Step A: Get your Library ID
1. Log into [zotero.org](https://www.zotero.org/settings/keys).
2. Go to **Settings > Feeds/API**.
3. Look for `Your userID` (it's a number like `1234567`). If you are using a group, you'll need the Group ID found in the group's URL on the Zotero website.

### Step B: Create an API Key
1. On that same page, click **[Create new private key]**.
2. Name it `ZoteroCLI`.
3. Check the boxes:
    *   [x] Personal Library: **Read/Write**
    *   [x] Default Group Permissions: **Read/Write**
4. Click **Save Key**.
5. You will see a long string of random characters. **Copy this immediately**—you won't see it again!

---

## 3. Installation
Verify the tool is installed by typing this command and pressing **Enter**:
```bash
zotero-cli --version
```
You should see: `zotero-cli v2.0.0`. If yes, you are ready!

---

## 4. The Easy Setup (Recommended)
The simplest way to connect is using the built-in configuration wizard.

Type this command:
```bash
zotero-cli init
```

The wizard will ask for:
1.  **Zotero API Key**: Paste the key you copied in Step B.
2.  **Library Type**: Choose `user` (for your own library) or `group` (for a shared group).
3.  **Library ID**: Enter your User ID or Group ID.
4.  **Optional Settings**: You can skip these by pressing Enter.

The tool will **verify** your connection automatically. If everything is correct, it will save your settings.

### Alternative: Environment Variables
For advanced users or temporary sessions, you can still use:
```bash
export ZOTERO_API_KEY="your_key"
export ZOTERO_LIBRARY_ID="12345"
```

---

## 5. Verify your Setup
Run this command to check your library status:
```bash
zotero-cli system info
```

**Success looks like this:**
```text
--- Zotero CLI Info ---
Config Path: /home/user/.config/zotero-cli/config.toml
Library ID:  1234567
Library Type: user
API Key:     ********
```

---

## 6. Your First List
Let's see your collections:

```bash
zotero-cli collection list
```

### Next Step
Ready to start a Systematic Review? Go to **[Tutorial 2: SLR Workflow](./02-slr-workflow.md)**.