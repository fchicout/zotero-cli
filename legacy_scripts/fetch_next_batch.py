import json

try:
    with open('cissa/xeque-mate/rsl-xm/02-Search/raw_arXiv_papers.json', 'r') as f:
        data = json.load(f)
    
    # Starting after the previous batch (266 + 5 = 271)
    start_index = 271
    batch_size = 20
    
    print(f"Total papers: {len(data)}")
    print(f"Starting from index: {start_index}")
    
    for i in range(start_index, min(start_index + batch_size, len(data))):
        paper = data[i]
        print(f"\n--- Item {i+1} ---")
        print(f"Key: {paper.get('key', 'N/A')}")
        print(f"Title: {paper.get('title', 'N/A')}")
        # Clean abstract to remove newlines for better readability in log
        abstract = paper.get('abstract', 'N/A').replace('\n', ' ')
        print(f"Abstract: {abstract[:400]}...") 
except Exception as e:
    print(f"Error: {e}")