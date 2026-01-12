
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
        {"key": "PSZ5N88T", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Jailbreak mimicry: Automated discovery of jailbreaks (Attack ON LLMs)."},
        {"key": "8QUIFA8Q", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "CLASP: LLM-based agentic system for phishing detection."},
        {"key": "3FF6R92B", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "L2M-AID: LLM-empowered agents for industrial defense (ICS/OT)."},
        {"key": "3FZDPBWK", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Multilingual multi-agent LLMs for misinformation detection."},
        {"key": "G4U5P9F9", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLM based blind DoS detection in 5G."},
        {"key": "9T4Q5HMN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "RHINO: Log analysis/Threat analysis using LLMs."},
        {"key": "JIMAER9H", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "XGen-Q: Explainable LLM framework for malware detection."},
        {"key": "MZDA8ZJE", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Zero-/few-shot LLMs for network intrusion detection."},
        {"key": "UNMF48WG", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "NegBLEURT forest: Detecting jailbreak attacks (Threat Detection)."},
        {"key": "HCTRC5SC", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Data poisoning vulnerabilities (Attack/Risk analysis)."},
        {"key": "DS3XTC5F", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Distributed security threat detection using multimodal LLMs."},
        {"key": "NEZCZPNZ", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Detecting dead code poisoning (Threat) in code datasets using perplexity."},
        {"key": "DHKUD3K2", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "SLM robustness to jailbreak attacks (Security OF AI)."},
        {"key": "75HWSCUH", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "CyLens: CTI copilot using LLMs (Threat attribution, detection)."},
        {"key": "A9E6E56I", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "RedChronos: LLM-based log analysis for insider threat detection."},
        {"key": "ZHAEW8BN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "AttackSeqBench: Benchmarking LLMs in analyzing attack sequences."},
        {"key": "R79I84PJ", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Privacy auditing of LLMs (Security OF AI)."},
        {"key": "VFABJS2Q", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "AuthorMist: Evading AI text detectors (Attack)."},
        {"key": "9J5QIEIC", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Visual prompts injection threats (Attack analysis)."},
        {"key": "ET3VQJKH", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLM agents for simulation and detection of social engineering."},
        {"key": "NF8823T5", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "EXPLICATE: Phishing detection with LLM-powered interpretability."},
        {"key": "S5ISKRFH", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLM-based provenance analysis for APT detection."},
        {"key": "QU6IBDAQ", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Training LLMs for typosquatting detection."},
        {"key": "XP4CFIPE", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "MIRAGE: Multimodal jailbreak attacks (Attack)."},
        {"key": "PSC862V5", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Encrypted prompt: Securing LLM applications (Defense FOR LLMs)."},
        {"key": "BSBC773U", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Adversarial attack detection using CLIP (Vision-Language Model)."},
        {"key": "VDWEZT4A", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Vulnerability analysis of LLM agents (Cross-Tool Harvesting)."},
        {"key": "5WGUTCM9", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Detecting abnormal behaviors IN LLMs via hidden state forensics."},
        {"key": "FHJQH4HF", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Hallucination-resistant vision-language model (Reliability)."},
        {"key": "M3HJFQKN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLM-assisted proactive threat intelligence."},
        {"key": "73U2ZB66", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Survey on resilient federated learning."},
        {"key": "PK4FCU32", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Survey/Synthesis of detecting AI-generated content."},
        {"key": "UKIN9L3C", "decision": "EXCLUDE", "reason_code": "EC9", "reason_text": "Metadata Error: Multiple DOIs found, N/A abstract."},
        {"key": "R2IGIS6M", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Detecting instruction fine-tuning attacks on LLMs."},
        {"key": "P4FZAW59", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Investigating cybersecurity incidents using LLMs in wireless networks."},
        {"key": "TNEPQ3PD", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Memory backdoor attacks on neural networks (Attack)."},
        {"key": "WHT7EAZM", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "ThreatModeling-LLM: Automating threat modeling using LLMs."},
        {"key": "C45JI8T5", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "TrafficLLM: Network traffic analysis for threat detection."},
        {"key": "RVQ7BRK8", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Comprehensive review of LLM-based approaches in malware code analysis."},
        {"key": "5V44CFH9", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "GenXSS: Automated detection of XSS attacks using LLMs."},
        {"key": "U2C6WKAQ", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "ControlNET: Firewall for RAG-based LLM systems (Detects adversarial queries)."},
        {"key": "7BPNF7KR", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "CleanVul: Automatic vulnerability detection in code commits using LLMs."},
        {"key": "A2QGHG86", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Enhanced LLM-based framework for predicting null pointer dereference."},
        {"key": "FDMJ253H", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "BDefects4NN: Backdoor defect database (Resource for detection studies)."},
        {"key": "ZKACVKAP", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Automated hardware trojan design using LLMs (Attack)."},
        {"key": "E8VM3CAM", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Model-editing-based jailbreak (Attack)."},
        {"key": "BERIF2CV", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Detecting unseen backdoored images using prompt tuning in VLMs."},
        {"key": "96ZXBXM8", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "SpearBot: Spear-phishing email generation (Attack)."},
        {"key": "J4PSAXXA", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Detecting sandbagging in LLMs (Capability Evaluation/Auditing)."},
        {"key": "DJP43PBI", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Unseen attack detection in SDN using BERT."}
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
