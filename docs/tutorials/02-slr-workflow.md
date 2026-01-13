# Tutorial 2: Your First Systematic Review (SLR)

**Audience:** Researchers conducting a Systematic Literature Review.
**Goal:** Screen 100 papers in 10 minutes using the "Tinder-for-Papers" interface.

---

## The Scenario
You just imported 500 papers from IEEE and ACM into a Zotero collection named `MyThesis_Search`. Now you need to decide which ones are relevant based on their **Title** and **Abstract**.

Usually, you would open each PDF, scroll, read, drag to a folder... slow.
Let's do it the `zotero-cli` way.

---

## Step 1: Find your Collection Key
First, let's see your collections to find the right code (Key).

```bash
zotero-cli collections
```

**Output:**
```text
Key      Name              Items
-------  ----------------  -----
ABC1234  MyThesis_Search   500
XYZ9876  Old_Project       23
```
*Okay, our target key is `ABC1234`.*

---

## Step 2: Start Screening
We will launch the interactive screen using the **TUI (Text User Interface)**.

```bash
zotero-cli screen ABC1234
```

The screen will change. You will see:
1.  **Top:** The Title of the paper (in bold).
2.  **Middle:** The Abstract.
3.  **Bottom:** Instructions.

### How to Control It
*   **[i]nclude:** Press `i` if the paper is **Relevant**. (It's a Keeper!)
*   **[e]xclude:** Press `e` if it's **Irrelevant**. (Throw it away).
*   **[u]ndecided:** Press `u` if you aren't sure yet.

### The "Why?" (Exclusion Criteria)
If you press **[e]**, the tool will ask "Why?". You can choose predefined codes:
*   `IC1`: Out of Scope
*   `IC2`: Not English
*   `IC3`: Not a Primary Study
*(These codes are customizable!)*

---

## Step 3: What happens in Zotero?
Go back to your Zotero desktop app. Look at the paper you just screened.
You will see a **Note** attached to it, looking like this:

```markdown
# AUDIT TRAIL
**Decision:** EXCLUDED
**Reason:** IC1 (Out of Scope)
**Phase:** 1 (Title/Abstract)
**Date:** 2026-01-13
```

**This is your proof.** You don't need Excel sheets anymore. Zotero is your database.

---

## Step 4: Generating the PRISMA Report
You finished screening 50 papers. Your advisor asks: "What's the status?"

Run this:
```bash
zotero-cli report --collection ABC1234
```

**Output:**
```text
PRISMA Screening Report
-----------------------
Total Papers: 50
Included:     12
Excluded:     38
  - IC1: 30
  - IC2: 8
Progress:     10% (50/500)
```

Take a screenshot and send it to your advisor. You're done for the day.
