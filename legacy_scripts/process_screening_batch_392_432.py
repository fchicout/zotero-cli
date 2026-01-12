
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
        {"key": "7ZIG2KGR", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "ConvoSentinel: Social engineering detection using modular LLM defense."},
        {"key": "N9G3HNCP", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "SecureNet: Comparative study of DeBERTa and LLMs for phishing detection."},
        {"key": "CPQMJEEN", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Attack on LLM watermarking (Security OF AI)."},
        {"key": "3VPMWUTE", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Unlearning misinformation IN LLMs (Model Safety/Alignment)."},
        {"key": "EWP86KPN", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "OOD detection in Math reasoning (Reliability/Safety of AI)."},
        {"key": "V9ZV9Q85", "decision": "EXCLUDE", "reason_code": "EC2", "reason_text": "Uses FastText embeddings (not LLM) for API anomaly detection."},
        {"key": "TS2ZB5R4", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Malware detection using transfer learning in LLMs (BigBird/Longformer)."},
        {"key": "UATR5VRF", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Distributed threat intelligence at the edge using LLMs."},
        {"key": "4X5SM4M3", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "AnomalyLLM: Graph anomaly detection using LLMs."},
        {"key": "Q2CRVKE5", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "CANAL: Cyber activity news alerting using BERT/LLMs (CTI)."},
        {"key": "CGJQUGC9", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Insider threat detection through data synthesis and analysis by LLMs."},
        {"key": "SDAQJKMN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLM-based real-time detection of phone scams."},
        {"key": "ZBKWKSND", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "AdaPhish: AI-powered adaptive defense/detection for phishing."},
        {"key": "ZM26HA2J", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLMSecConfig: LLM-based fixing of container misconfigurations (Vulnerability Response)."},
        {"key": "X27ZH7RV", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Multilingual cyber threat detection in tweets using LLMs."},
        {"key": "IJM78IH7", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Synthetic user behavior generation with LLMs for smart home security (Data Gen)."},
        {"key": "WNTE6Z4X", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Backdoor defense IN LLMs (Security OF AI)."},
        {"key": "JMR4VGHR", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Adversarial robustness of PLMs (Security OF AI)."},
        {"key": "CIMH5TXI", "decision": "EXCLUDE", "reason_code": "EC2", "reason_text": "Detecting fake stars (StarScout). Likely statistical/graph analysis, not LLM-based detection."},
        {"key": "BRXED658", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "AI-based attacker models (LLM) for cyberattack simulation (Testing/Detection support)."},
        {"key": "VDC7MPUV", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Evaluating LLMs as phishing detection tools."},
        {"key": "TS8AZ6SU", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Attack on RAG-based LLMs (PR-attack)."},
        {"key": "77ANGV9I", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Survey on Machine Learning in IDS for IoT."},
        {"key": "EGFRBHS4", "decision": "EXCLUDE", "reason_code": "EC2", "reason_text": "SINCon: Defense against LLM attacks using Contrastive Learning (Likely GNN, not LLM defense)."},
        {"key": "9IIEV76T", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "AttackLLM: LLM-based attack pattern generation for ICS (Robustness evaluation)."},
        {"key": "VHBVFEW3", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "STING-BEE: Vision-language model for X-ray baggage security inspection."},
        {"key": "92DCM7MC", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Integrated LLM-based intrusion detection for O-RAN."},
        {"key": "JJB7MBX2", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "DB-less Software Composition Analysis (SCA) using LLMs."},
        {"key": "KC89JEUH", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Debate-driven multi-agent LLMs for phishing email detection."},
        {"key": "BWX2BMQT", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "DroidTTP: Mapping Android malware to TTPs using LLMs."},
        {"key": "III4JCUS", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Forensics-Bench: Benchmark for forgery detection using LVLMs."},
        {"key": "BAPJZTME", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Enforcing security constraints for LLM-driven robot agents (Response/Prevention)."},
        {"key": "IH8GG656", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Adaptive fault tolerance of LLMs (Reliability/Efficiency, not threat detection)."},
        {"key": "RWRRW6QC", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Adapting LLMs for log anomaly detection (PEFT)."},
        {"key": "N49TCWSS", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Vulnerability analysis of LLM-based Text-to-SQL (ToxicSQL)."},
        {"key": "9AXM3BEN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Enhancing cybersecurity in critical infrastructure with LLM-assisted explainable IoT systems."},
        {"key": "EWW62EA2", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "OMNISEC: LLM-driven provenance-based intrusion detection."},
        {"key": "FN8NZ5AB", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Backdoor attack in vision encoders for LVLMs (Attack)."},
        {"key": "QEIWN94N", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Guardians of the agentic system: Anti-jailbreaking system using agents."},
        {"key": "KJA9SQGI", "decision": "EXCLUDE", "reason_code": "EC2", "reason_text": "KillBadCode: Uses n-gram language models (Not LLM)."},
        {"key": "JFQ5MIMR", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LAMD: Context-driven Android malware detection with LLMs."}
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
