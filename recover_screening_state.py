import csv
import subprocess
import re
import sys
import json

def run_command(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except Exception as e:
        return None

def recover_state(csv_path):
    print("Fetching included items from Zotero (screening_sciencedirect B73259TE)...")
    included_raw = run_command(['zotero-cli', 'list', 'items', '--collection', 'B73259TE'])
    included_keys = set(re.findall(r'([A-Z0-9]{8})', included_raw)) if included_raw else set()
    print(f"Found {len(included_keys)} included items.")

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))
        fieldnames = ['key', 'title', 'veredict', 'code', 'reason']

    print("Checking first 600 items for existing decisions...")
    
    for i, row in enumerate(reader[:600]):
        key = row['key']
        
        # Optimization: if already in included collection, mark it
        if key in included_keys:
            row['veredict'] = 'INCLUDE'
            row['code'] = 'IC1'
            row['reason'] = 'Confirmed in screening collection'
            continue
        
        # Inspect for note
        output = run_command(['zotero-cli', 'inspect', '--key', key])
        if output:
            # Look for JSON block in notes
            # The inspect output shows Children (1): - <div>{ ... }
            json_match = re.search(r'\{.*"decision":\s*"(.*?)".*?"code":\s*"(.*?)".*?"reason":\s*"(.*?)".*?\}', output, re.DOTALL)
            if json_match:
                row['veredict'] = json_match.group(1).upper()
                row['code'] = json_match.group(2)
                row['reason'] = json_match.group(3).strip()
                # print(f"[{i+1}] {key}: {row['veredict']}")
            else:
                # Try simple match if JSON parser fails or format is slightly different
                simple_match = re.search(r'Vote:\s+(INCLUDE|EXCLUDE)\s+Code:\s+([A-Z0-9]+)\s+Reason:\s+(.*)', output)
                if simple_match:
                    row['veredict'] = simple_match.group(1)
                    row['code'] = simple_match.group(2)
                    row['reason'] = simple_match.group(3).strip()

        if (i+1) % 50 == 0:
            print(f"Processed {i+1}/600...")

    # Verification: Count recovered
    recovered = [r for r in reader if r['veredict']]
    print(f"Recovery complete. Total decisions found: {len(recovered)}")

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(reader)

if __name__ == "__main__":
    recover_state('cissa/tools/zotero-cli/sciencedirect_screening.csv')
