
import os
import sys
import json
import datetime
from zotero_cli.infra.zotero_api import ZoteroAPIClient

def process_batch():
    api_key = os.environ.get("ZOTERO_API_KEY")
    library_id = os.environ.get("ZOTERO_LIBRARY_ID")
    
    if not api_key or not library_id:
        print("Error: ZOTERO_API_KEY and ZOTERO_LIBRARY_ID must be set.")
        sys.exit(1)

    client = ZoteroAPIClient(api_key, library_id)
    target_collection = "5DA6C9A3" # screening_arXiv

    decisions = [
        {"key": "AZ3EZJZB", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Explicit LLM-based Intrusion Detection."},
        {"key": "996Z25DT", "decision": "EXCLUDE", "reason_code": "IC1", "reason_text": "Attack on MLLMs (Adversarial AI). Review of attacks/defenses for MLLM safety."},
        {"key": "IGCMHNIR", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Uses companion LLM to detect Prompt Injection attacks."},
        {"key": "QKE76NRU", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Uses LLM Embeddings to detect Prompt Injection."},
        {"key": "NZQPPCHG", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Proposes a prompt guard model (Detector) for Prompt Injection."},
        {"key": "GDIUX8BS", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Uses LLMs to generate phishing for training detectors."},
        {"key": "C26CUW8W", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Uses LLM for Hacker Identification (Threat Intelligence/Attribution)."},
        {"key": "Z9HCE7SB", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Uses BERT to detect app cloning/squatting."},
        {"key": "PD3P67H9", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Uses LLM for Attack Graph construction (Threat Analysis support)."},
        {"key": "ZB5TVUZ4", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Uses LLM to derive Knowledge Graph for Anomaly Detection (VAD)."},
        {"key": "BZAVGGWV", "decision": "EXCLUDE", "reason_code": "IC1", "reason_text": "Measuring Awareness OF LLMs (LLM Safety/Capability evaluation)."},
        {"key": "2GVVFZJ3", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Explicit LLM-based Phone Scam Detection."},
        {"key": "PWFB987M", "decision": "EXCLUDE", "reason_code": "IC1", "reason_text": "Attack on LLM systems (Side Channel)."},
        {"key": "C9E99PIC", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Enhancing LLM-based Vulnerability Detection."},
        {"key": "S6I8PMRK", "decision": "EXCLUDE", "reason_code": "IC1", "reason_text": "Detection of attacks on watermarks (Spoofing). LLM Security."},
        {"key": "9NFDDJNV", "decision": "EXCLUDE", "reason_code": "IC1", "reason_text": "IP Protection/Fingerprinting of LLMs."},
        {"key": "KI4ACKJV", "decision": "EXCLUDE", "reason_code": "IC1", "reason_text": "Risk assessment OF GenAI models."},
        {"key": "CSK7Z56I", "decision": "EXCLUDE", "reason_code": "IC1", "reason_text": "Securing GenAI (Red/Blue teaming OF LLMs)."},
        {"key": "ACXX3BIB", "decision": "EXCLUDE", "reason_code": "IC1", "reason_text": "Detecting memorization in LLMs (Privacy/Safety of the model)."},
        {"key": "S7PXRPES", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Evaluates LLM capability for Scam Detection."}
    ]

    for item in decisions:
        print(f"Processing {item['key']}...")
        note_content = {
            "step": "screening_title_abstract",
            "reviewer": "Dr. Vance (Gemini)",
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

if __name__ == "__main__":
    process_batch()
