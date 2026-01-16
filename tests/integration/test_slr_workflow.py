import os
import pytest
import subprocess
import time
import re
import json
import csv
from pathlib import Path

# Integration tests interact with the REAL Zotero API.
# Ensure ZOTERO_API_KEY and ZOTERO_USER_ID (or ZOTERO_TARGET_GROUP) are set.

def run_cli(args):
    """Helper to run zotero-cli and return output/exit code."""
    cmd = ["zotero-cli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

def extract_keys(text):
    """Extracts 8-char Zotero keys from rich table output."""
    return re.findall(r"│ ([A-Z0-9]{8}) │", text)

@pytest.mark.integration
def test_iron_gauntlet_slr():
    ts = int(time.time())
    col_src = f"E2E_Source_{ts}"
    col_mir = f"E2E_Mirror_{ts}"
    csv_path = f"tests/integration/bulk_decisions_{ts}.csv"
    snap_path = f"tests/integration/snapshot_{ts}.json"
    report_path = f"tests/integration/report_{ts}.md"
    status_path = f"tests/integration/status_{ts}.md"
    local_pdf = "/home/fcfmc/Downloads/13040_2021_Article_244.pdf"
    
    collections_to_cleanup = [col_src, col_mir]
    
    try:
        # 1. Create Collections
        print(f"\n[1/8] Creating collections: {col_src}, {col_mir}")
        assert run_cli(["collection", "create", col_src]).returncode == 0
        assert run_cli(["collection", "create", col_mir]).returncode == 0
        
        # 2. Import same paper to both
        print("[2/8] Importing probe paper...")
        import_cmd = ["import", "arxiv", "--query", "ti:Attention Is All You Need", "--limit", "1"]
        assert run_cli(import_cmd + ["--collection", col_src]).returncode == 0
        assert run_cli(import_cmd + ["--collection", col_mir]).returncode == 0
        
        # Get Keys
        res_src = run_cli(["item", "list", "--collection", col_src])
        keys_src = extract_keys(res_src.stdout)
        assert keys_src
        item_key = keys_src[0]

        # 3. Duplicate Detection
        print("[3/8] Verifying duplicate detection...")
        res = run_cli(["collection", "duplicates", "--collections", f"{col_src},{col_mir}"])
        assert item_key in res.stdout

        # 4. Metadata Hardening
        print("[4/8] Hardening metadata...")
        run_cli(["item", "update", item_key, "--doi", "10.48550/arXiv.1706.03762"])
        if os.path.exists(local_pdf):
            run_cli(["item", "pdf", "attach", item_key, local_pdf])
        
        # 5. Bulk Decision via CSV
        print("[5/8] Executing bulk decisions...")
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Key", "Vote", "Reason"])
            writer.writerow([item_key, "INCLUDE", "Iron Gauntlet Bulk Test"])
        
        res = run_cli(["review", "screen", "--source", col_src, "--include", col_src, "--exclude", col_mir, "--file", csv_path])
        assert "Success: 1" in res.stdout

        # 6. Reporting (Dummy Collection)
        print("[6/8] Reporting on dummy collection...")
        assert run_cli(["report", "prisma", "--collection", col_src]).returncode == 0
        assert run_cli(["report", "snapshot", "--collection", col_src, "--output", snap_path]).returncode == 0
        assert run_cli(["report", "screening", "--collection", col_src, "--output", report_path]).returncode == 0
        assert run_cli(["report", "status", "--collection", col_src, "--output", status_path]).returncode == 0
        assert os.path.exists(report_path)
        assert os.path.exists(status_path)

        # 7. Reporting (Existing Research Collections - READ ONLY)
        print("[7/8] Verifying reporting on research collections (raw_arXiv, screening_arXiv)...")
        # Note: We assume these collections exist in the target library. 
        # If not, the test will skip or warn, but won't fail the gauntlet if it's environment-specific.
        for coll in ["raw_arXiv", "screening_arXiv"]:
            res = run_cli(["report", "prisma", "--collection", coll])
            if res.returncode == 0:
                print(f"      ✓ PRISMA verified for {coll}")
                tmp_md = f"tests/integration/tmp_{coll}.md"
                assert run_cli(["report", "screening", "--collection", coll, "--output", tmp_md]).returncode == 0
                if os.path.exists(tmp_md): os.remove(tmp_md)
            else:
                print(f"      ! Collection {coll} not found or inaccessible. Skipping validation.")

        # 8. Destructive: Clean Mirror
        print("[8/8] Verifying collection clean...")
        assert run_cli(["collection", "clean", "--collection", col_mir]).returncode == 0
        assert "Showing 0 items" in run_cli(["item", "list", "--collection", col_mir]).stdout

    finally:
        # Cleanup
        print(f"\n--- Final Purge ---")
        for col in collections_to_cleanup:
            run_cli(["collection", "delete", col, "--recursive"])
        
        for p in [csv_path, snap_path, report_path, status_path]:
            if os.path.exists(p):
                os.remove(p)
