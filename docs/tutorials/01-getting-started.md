# Tutorial 1: Getting Started with Zotero CLI

**Audience:** Researchers, Students, and anyone who loves Zotero but is new to the Command Line.
**Goal:** Connect this tool to your Zotero account and run your first command.

---

## 1. What is this tool?
Think of `zotero-cli` as a "Super Plugin" that lives outside of Zotero. It helps you:
*   **Screen papers** faster (using keyboard shortcuts).
*   **Clean up** your metadata.
*   **Generate reports** automatically.

It runs in a black window called the **Terminal**, but don't worry—we'll guide you through every keystroke.

## 2. Prerequisites (The Boring Stuff)
Before we start, you need two things from the Zotero website:

### Step A: Get your User ID
1. Log into [zotero.org](https://www.zotero.org/settings/keys).
2. Go to **Settings > Feeds/API**.
3. Look for `Your userID` (it's a number like `1234567`).
4. **Write this down.**

### Step B: Create a Key
1. On that same page, click **[Create new private key]**.
2. Name it `ZoteroCLI`.
3. Check the boxes:
    *   [x] Personal Library: **Read/Write**
    *   [x] Default Group Permissions: **Read/Write**
4. Click **Save Key**.
5. You will see a long string of random characters (e.g., `H8d9...`). **Copy this immediately**—you won't see it again!

---

## 3. Installation
(Ask your IT friend or use the installer provided by the developer).
*Assuming you have the tool installed and opened the terminal:*

Type this command and press **Enter**:
```bash
zotero-cli --version
```
You should see: `zotero-cli v0.4.0`. If yes, you are ready!

---

## 4. The First Connection
Now, let's introduce the tool to your library. We will set the "Environment Variables" (a fancy way of saving your password).

**Mac/Linux:**
```bash
export ZOTERO_USER_ID="1234567"
export ZOTERO_API_KEY="your_long_key_here"
```

**Windows (PowerShell):**
```powershell
$env:ZOTERO_USER_ID="1234567"
$env:ZOTERO_API_KEY="your_long_key_here"
```

### Test it!
Run this command to check your library info:
```bash
zotero-cli info
```

**Success looks like this:**
```text
Zotero Library Info:
--------------------
User ID: 1234567
Type:    user
Items:   1,420
Groups:  Research Team A, Thesis Group
```

---

## 5. Your First "Magic Trick"
Let's find the stats of your library report.

```bash
zotero-cli report
```

The tool will scan your screening decisions (if any) and show you a table. Since you are new, it might say "No screening data found"—and that's okay! It proves the connection works.

### Next Step
Ready to do real work? Go to **[Tutorial 2: Screening Papers](./02-slr-workflow.md)**.
