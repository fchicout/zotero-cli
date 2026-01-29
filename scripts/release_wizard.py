#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime

# --- Configuration ---
DRAFT_FILE = "RELEASE_DRAFT.md"

def run(cmd, cwd=None, capture=True):
    """Run a shell command."""
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None
    )
    return result

def check_hygiene():
    """Ensure workspace is clean."""
    print("🧹 Checking Workspace Hygiene...")
    res = run("git status --porcelain")
    if res.stdout.strip():
        print("❌ CRITICAL: Workspace is dirty. Commit or stash changes first.")
        print(res.stdout)
        sys.exit(1)
    print("✅ Workspace is clean.")

def get_last_tag():
    """Get the latest tag."""
    res = run("git describe --tags --abbrev=0")
    if res.returncode != 0:
        return None
    return res.stdout.strip()

def generate_notes(last_tag, new_version):
    """Generate release notes from git log."""
    print(f"📝 Generating Release Notes ({last_tag} -> HEAD)...")

    range_spec = f"{last_tag}..HEAD" if last_tag else "HEAD"
    cmd = f'git log {range_spec} --pretty=format:"%s"'
    res = run(cmd)

    commits = res.stdout.splitlines()

    # Categorize
    categories = {
        "feat": [],
        "fix": [],
        "docs": [],
        "chore": [],
        "other": []
    }

    for line in commits:
        match = re.match(r"^(\w+)(?:\(.*?\))?: (.*)", line)
        if match:
            ctype, msg = match.groups()
            if ctype in categories:
                categories[ctype].append(msg)
            else:
                categories["other"].append(line)
        else:
            categories["other"].append(line)

    # Build Markdown
    lines = [f"# Release {new_version}", "", f"**Date:** {datetime.now().strftime('%Y-%m-%d')}", ""]

    if categories["feat"]:
        lines.append("## 🚀 Features")
        for item in categories["feat"]:
            lines.append(f"- {item}")
        lines.append("")

    if categories["fix"]:
        lines.append("## 🐛 Bug Fixes")
        for item in categories["fix"]:
            lines.append(f"- {item}")
        lines.append("")

    if categories["docs"]:
        lines.append("## 📚 Documentation")
        for item in categories["docs"]:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Argentis Release Wizard")
    parser.add_argument("version", help="New version tag (e.g., v2.3.0)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing tag")
    args = parser.parse_args()

    version = args.version
    if not version.startswith("v"):
        version = f"v{version}"

    # 1. Hygiene Check
    check_hygiene()

    # 2. Check for existing Draft
    notes = ""
    if os.path.exists(DRAFT_FILE):
        print(f"📄 Found existing {DRAFT_FILE}.")
        choice = input("Reuse this draft? [Y/n]: ").strip().lower()
        if choice in ("", "y"):
            with open(DRAFT_FILE, "r") as f:
                notes = f.read()

    if not notes:
        last_tag = get_last_tag()
        notes = generate_notes(last_tag, version)
        with open(DRAFT_FILE, "w") as f:
            f.write(notes)
        print(f"💾 Draft saved to {DRAFT_FILE}. Review it now if needed.")

    print("\n--- RELEASE PREVIEW ---")
    print(notes)
    print("-----------------------\n")

    if input(f"🚀 Release {version}? [y/N]: ").strip().lower() != "y":
        print("Aborted.")
        sys.exit(0)

    # 3. Tagging
    # Check if tag exists
    check_tag = run(f"git rev-parse {version}")
    if check_tag.returncode == 0:
        if args.force:
            print(f"⚠️ Overwriting existing tag {version}...")
            run(f"git tag -d {version}")
            run(f"git push --delete origin {version}")
        else:
            print(f"❌ Tag {version} already exists. Use --force to overwrite.")
            sys.exit(1)

    print("🏷️ Tagging...")
    run(f"git tag -a {version} -F {DRAFT_FILE}")

    print("⬆️ Pushing...")
    res = run(f"git push origin {version}")
    if res.returncode != 0:
        print("❌ Push failed.")
        print(res.stderr)
        sys.exit(1)

    print("✅ Done! CI/CD should trigger now.")
    # Optional: cleanup draft
    # os.remove(DRAFT_FILE)

if __name__ == "__main__":
    main()
