import os
import sys
import json
import datetime

# Add the directory containing zotero_cli (src) to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from zotero_cli.infra.zotero_api import ZoteroAPIClient

def process_batch():
    api_key = os.environ.get("ZOTERO_API_KEY")
    library_id = os.environ.get("ZOTERO_LIBRARY_ID")
    
    if not api_key or not library_id:
        print("Error: ZOTERO_API_KEY and ZOTERO_LIBRARY_ID must be set.")
        sys.exit(1)

    client = ZoteroAPIClient(api_key, library_id)
    target_collection = "5DA6C9A3" 

    decisions = [
        {"key": "P65E45ZF", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Security OF AI: Focuses on the security of the backbone LLM itself (adversarial attacks)."},
        {"key": "6EZG7DHD", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Security BY AI: Explicitly uses LLMs for DDoS detection and mitigation rule generation."},
        {"key": "H6QVJ2NK", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Secondary Study: SoK (Systematization of Knowledge)."},
        {"key": "TKWPPPTA", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "IP Protection: Focuses on watermarking and provenance (Security OF AI)."},
        {"key": "WTPEIT8X", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Model Theft: Focuses on preventing model exfiltration (Security OF AI)."}
    ]

    for item in decisions:
        print(f"Processing {item['key']}...")
        note_content = {
            "step": "screening_title_abstract",
            "reviewer": "Dr. Silas (Gemini)",
            "decision": item['decision'],
            "reason_code": item['reason_code'],
            "reason_text": item['reason_text'],
            "timestamp": datetime.datetime.now().isoformat()
        }
        note_html = f"<pre>{json.dumps(note_content, indent=2)}</pre>"
        payload = {
            "itemType": "note",
            "parentItem": item['key'],
            "note": note_html,
            "tags": [{"tag": f"screening:{item['decision'].lower()}"}]
        }
        try:
            url = f"{client.BASE_URL}/groups/{client.group_id}/items"
            res = client.session.post(url, json=[payload])
            res.raise_for_status()
            print(f"  - Note created.")
        except Exception as e:
            print(f"  - Error creating note: {e}")

        if item['decision'] == "INCLUDE":
            try:
                z_item = client.get_item(item['key'])
                if z_item:
                    current_collections = z_item.collections
                    if target_collection not in current_collections:
                        current_collections.append(target_collection)
                        success = client.update_item_collections(item['key'], z_item.version, current_collections)
                        if success:
                            print(f"  - Moved to screening_arXiv.")
                        else:
                            print(f"  - Failed to move.")
                    else:
                        print(f"  - Already in collection.")
            except Exception as e:
                print(f"  - Error moving item: {e}")

if __name__ == "__main__":
    process_batch()