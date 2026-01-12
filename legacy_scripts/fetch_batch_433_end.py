
import json
import os

try:
    with open('cissa/xeque-mate/rsl-xm/02-Search/raw_arXiv_papers.json', 'r') as f:
        data = json.load(f)
    
    start_index = 432
    # Fetch all remaining items
    output_path = 'cissa/tools/zotero-cli/tmp/batch_433_end.txt'
    
    with open(output_path, 'w') as out:
        out.write(f"Total papers: {len(data)}\n")
        out.write(f"Starting from index: {start_index}\n")
        
        for i in range(start_index, len(data)):
            paper = data[i]
            out.write(f"\n--- Item {i+1} ---\n")
            out.write(f"Key: {paper.get('key', 'N/A')}\n")
            out.write(f"Title: {paper.get('title', 'N/A')}\n")
            abstract = paper.get('abstract')
            if abstract:
                abstract = abstract.replace('\n', ' ')
            else:
                abstract = "N/A"
            out.write(f"Abstract: {abstract}\n")
            
    print(f"Batch written to {output_path}")

except Exception as e:
    print(f"Error: {e}")
