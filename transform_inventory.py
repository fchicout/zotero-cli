import csv
import sys
import re

def parse_raw_inventory(input_file, output_csv):
    # Regex to capture the table rows
    # Example line: │    1 │ One for all: LLM-based heterogeneous mission planning in precision agriculture   │ 6RHCCHK8 │ journalArticle │
    row_pattern = re.compile(r'│\s+\d+\s+│\s+(.*?)\s+│\s+([A-Z0-9]{8})\s+│\s+(.*?)\s+│')
    
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    data = []
    for line in lines:
        match = row_pattern.search(line)
        if match:
            title = match.group(1).strip()
            key = match.group(2).strip()
            # item_type = match.group(3).strip()
            data.append({
                'key': key,
                'title': title,
                'veredict': '',
                'code': '',
                'reason': ''
            })
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['key', 'title', 'veredict', 'code', 'reason'])
        writer.writeheader()
        writer.writerows(data)
    
    print(f"Successfully created {output_csv} with {len(data)} items.")

if __name__ == "__main__":
    parse_raw_inventory('cissa/tools/zotero-cli/sd_inventory_raw.txt', 'cissa/tools/zotero-cli/sciencedirect_screening.csv')
