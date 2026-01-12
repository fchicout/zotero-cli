
import os
import sys
import json
import re
from datetime import datetime

# Add the directory containing zotero_cli (src) to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from zotero_cli.infra.zotero_api import ZoteroAPIClient

def generate_report():
    api_key = os.environ.get("ZOTERO_API_KEY")
    library_id = os.environ.get("ZOTERO_LIBRARY_ID")
    
    if not api_key or not library_id:
        print("Error: ZOTERO_API_KEY and ZOTERO_LIBRARY_ID must be set.")
        sys.exit(1)

    client = ZoteroAPIClient(api_key, library_id)
    raw_arxiv_key = "TYBTMHDI"
    
    print(f"Fetching items from raw_arXiv ({raw_arxiv_key})...")
    # Fetch all items (this might take a while and return notes/attachments too)
    all_items = list(client.get_items_in_collection(raw_arxiv_key))
    print(f"Total items found (including children): {len(all_items)}")
    
    # Filter for parent items (papers)
    papers = []
    excluded_types = ['note', 'attachment']
    
    for item in all_items:
        if item.item_type in excluded_types:
            continue
        papers.append(item)
        
    print(f"Total papers found: {len(papers)}")
    
    results = []
    
    for i, item in enumerate(papers):
        title = item.title if item.title else "No Title"
        # Truncate title for log
        log_title = (title[:30] + '...') if len(title) > 30 else title
        print(f"Processing item {i+1}/{len(papers)}: {log_title}")
        
        # Get children (notes) to find the screening decision
        children = client.get_item_children(item.key)
        decision_data = None
        
        for child in children:
            if child.get('data', {}).get('itemType') == 'note':
                note_content = child['data']['note']
                # Look for JSON block <pre>(...)</pre>
                match = re.search(r'<pre>(.*?)</pre>', note_content, re.DOTALL)
                if match:
                    try:
                        json_str = match.group(1)
                        # Clean up HTML entities
                        json_str = json_str.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                        data = json.loads(json_str)
                        if data.get('step') == 'screening_title_abstract':
                            decision_data = data
                            break
                    except json.JSONDecodeError:
                        print(f"  - Failed to decode JSON in note for {item.key}")
        
        status = "Pending"
        reason = "N/A"
        code = "N/A"
        reviewer = "N/A"
        
        if decision_data:
            status = decision_data.get('decision', 'Unknown')
            reason = decision_data.get('reason_text', 'N/A')
            code = decision_data.get('reason_code', 'N/A')
            reviewer = decision_data.get('reviewer', 'N/A')
        
        results.append({
            "key": item.key,
            "title": title,
            "status": status,
            "code": code,
            "reason": reason,
            "reviewer": reviewer
        })

    # Generate Markdown Report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    included_count = sum(1 for r in results if r['status'] == 'INCLUDE')
    excluded_count = sum(1 for r in results if r['status'] == 'EXCLUDE')
    pending_count = sum(1 for r in results if r['status'] == 'Pending')
    
    report = f"""# arXiv Screening Report (Title & Abstract)

**Date:** {timestamp}
**Source Collection:** `raw_arXiv` ({raw_arxiv_key})
**Total Items:** {len(results)}

## Summary
| Status | Count | Percentage |
| :--- | :--- | :--- |
| **Included** | {included_count} | {included_count/len(results)*100:.1f}% |
| **Excluded** | {excluded_count} | {excluded_count/len(results)*100:.1f}% |
| **Pending** | {pending_count} | {pending_count/len(results)*100:.1f}% |

## Exclusion Criteria Breakdown
"""
    
    # Calculate EC breakdown
    ec_counts = {}
    for r in results:
        if r['status'] == 'EXCLUDE':
            code = r['code']
            # Sometimes code might be a list or string, normalize
            if isinstance(code, list):
                code = ", ".join(code)
            ec_counts[code] = ec_counts.get(code, 0) + 1
            
    report += "| Criteria | Count |\n| :--- | :--- |\n"
    for code, count in sorted(ec_counts.items(), key=lambda x: x[1], reverse=True):
        report += f"| {code} | {count} |\n"

    report += "\n## Detailed Results\n\n| Key | Title | Decision | Code | Reason |\n| :--- | :--- | :--- | :--- | :--- |\n"
    
    for r in results:
        title_sanitized = r['title'].replace('|', '-').replace('\n', ' ')
        if len(title_sanitized) > 100:
            title_sanitized = title_sanitized[:97] + "..."
        reason_sanitized = str(r['reason']).replace('|', '-').replace('\n', ' ')
        if len(reason_sanitized) > 100:
            reason_sanitized = reason_sanitized[:97] + "..."
            
        report += f"| {r['key']} | {title_sanitized} | {r['status']} | {r['code']} | {reason_sanitized} |\n"
        
    output_path = "cissa/xeque-mate/rsl-xm/03-Screening/arXiv_Screening_Report.md"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding='utf-8') as f:
        f.write(report)
        
    print(f"Report generated at {output_path}")

if __name__ == "__main__":
    generate_report()
