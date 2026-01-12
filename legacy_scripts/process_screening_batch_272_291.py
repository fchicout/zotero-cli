
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
        {"key": "4GEUM4UQ", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Uses LLMs for data poisoning detection and sanitization in IoT (Role Play/CoT)."},
        {"key": "EA35ZJSN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "RAG-based framework for cybersecurity threat detection."},
        {"key": "RGW6J7XN", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Steganography/Covert communication (Not Threat Detection)."},
        {"key": "SMA7UFZ9", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Integration of LLMs into cybersecurity tools/IDS."},
        {"key": "35FNGCDU", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Analyzes an 'LLM-based threat detection and mitigation framework'."},
        {"key": "APJ99UQI", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Dataset (MH-1M) for LLM-based malware research."},
        {"key": "7WCF86MJ", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "MCPGuard: Vulnerability detection in MCP servers (agentic auditing)."},
        {"key": "KT8NU6PD", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Vision-LLMs for anomalous event detection in video."},
        {"key": "7HNPVT92", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLMLogAnalyzer: Log analysis chatbot for breach prevention."},
        {"key": "9SMWFZ9I", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Safety of LLMs (Self-Improving Safety Framework). Security OF AI."},
        {"key": "24IMUJDP", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Generating harmful audio (Attack/Risk)."},
        {"key": "3JJIX7N3", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Prompt injection attack on agents (Security OF AI)."},
        {"key": "KFJ6U2BB", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Unified Threat Detection framework (UTDMF) for prompt injection/deception."},
        {"key": "RBPBES5G", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "CTIArena: Benchmarking LLM for Cyber Threat Intelligence."},
        {"key": "EB58PGXI", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLM-powered AI agent framework for IoT traffic interpretation."},
        {"key": "JRG9BAH2", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Image manipulation detection using MLLMs (In-Context Forensic Chain)."},
        {"key": "FPD9RJ44", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Backdoor detection IN LLMs (Security OF AI)."},
        {"key": "2VZ8PWT3", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Attack technique (Living off the LLM)."},
        {"key": "CBCAVI2P", "decision": "EXCLUDE", "reason_code": "EC2", "reason_text": "Uses traditional ML/NLP for phishing detection, not LLMs. Detects LLM-generated phishing."},
        {"key": "MNS8UIEQ", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Proof-of-Training for backdoor detection IN LLMs (Security OF AI)."}
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
