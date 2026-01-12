
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
        {"key": "KSEQ4RWP", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Labeling NIDS rules with MITRE ATT&CK using LLMs."},
        {"key": "DPG2MSKF", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "BotSim: LLM-powered botnet simulation for benchmarking detection."},
        {"key": "NM9GN5MF", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Attack/Vulnerability analysis of LLMs (Human-readable adversarial prompts)."},
        {"key": "NITZ9DSU", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Invisible textual backdoor attacks (Attack)."},
        {"key": "6KW2756M", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "U-GIFT: Toxic speech detection using PLMs/BNNs."},
        {"key": "ANGS9ZKE", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "BARTPredict: Intrusion prediction using BART/BERT."},
        {"key": "8E5UHVFB", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Public facility failure management (Not cyber threat detection)."},
        {"key": "4MFJ2U6X", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Unified framework for IoT management and anomaly detection (fine-tuned model)."},
        {"key": "FWD2SB7X", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Report/Survey on LLM security challenges."},
        {"key": "FJ94XP62", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Thesis/Survey on AI in secure software engineering."},
        {"key": "WQ8HPM77", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "SpaLLM-guard: SMS spam detection using LLMs."},
        {"key": "8F5NQEEJ", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Network threat detection by knowledge graph and LLM."},
        {"key": "D9AZM26V", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "TORCHLIGHT: Detecting attacks on cloudless IoT using LLMs (CoT)."},
        {"key": "DAGJUFQH", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Survey on diffusion models for anomaly detection."},
        {"key": "J557TF6S", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Real-time fraud detection using RAG-based LLMs."},
        {"key": "H2VQQIR3", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Prompt injection attacks in federated military LLMs (Risk analysis)."},
        {"key": "QB4AV2NU", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "SHIELD: APT detection and explanation using LLM."},
        {"key": "M2R7FZN4", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "HateBench: Benchmarking hate speech detectors on LLM-generated content."},
        {"key": "67HTIQ9J", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "BounTCHA: CAPTCHA utilizing generative AI to detect bots."},
        {"key": "XJCCZAQU", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Rule-ATT&CK Mapper (RAM): Mapping SIEM rules to TTPs using LLMs."},
        {"key": "4WJ3AHK3", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Aero-LLM: Secure UAV communication and anomaly detection."},
        {"key": "C4RXBMNM", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Confidence elicitation: New attack vector for LLMs."},
        {"key": "4AUPSBAW", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Enhancing phishing email identification with LLMs."},
        {"key": "3ANNW7VM", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Copyright protection/Watermarking (Security OF AI)."},
        {"key": "KEC7DX4R", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "JBShield: Defending LLMs from jailbreak attacks (Detection/Mitigation)."},
        {"key": "29TSSJCH", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Framework for jailbreaking via obfuscating intent (Attack)."},
        {"key": "HVH4TTR3", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "SLR: Large language models for cyber security."},
        {"key": "IX2R6FJM", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "PLLM-CS: Pre-trained LLM for cyber threat detection in satellite networks."},
        {"key": "87WVF9IC", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "ExplainableDetector: SMS spam detection using Transformer-based LLMs."},
        {"key": "U3A5P2FA", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "DoLLM: DDoS detection using LLMs on network flow data."},
        {"key": "BQMHHFF2", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLMPot: LLM-based honeypot for industrial protocols."},
        {"key": "H7K8IFXQ", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Metamorphic malware evolution using LLMs (Attack generation)."},
        {"key": "PNGDFJGQ", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Code mutation training for LLMs (Attack generation)."},
        {"key": "JMWRWWK6", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Fine-tuning LLMs for DGA and DNS exfiltration detection."},
        {"key": "TEDHR44N", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "DFEPT: Data flow embedding for enhancing pre-trained model vulnerability detection."},
        {"key": "UBVTD4X6", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Enhancing prompt injection attacks via poisoning alignment."},
        {"key": "PJRKIEX3", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "PILLAR: LINDDUN privacy threat modeling using LLMs."},
        {"key": "GPKFKMVG", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "DomainLynx: Domain squatting detection using LLMs."},
        {"key": "UXSFQHBJ", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Survey on mitigating backdoor threats to LLMs."},
        {"key": "FGF9VSD6", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "MoJE: Mixture of jailbreak experts for prompt attack detection."},
        {"key": "WZTSNGDW", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Adaptive IoT security framework using XAI and LLMs."},
        {"key": "VMEX45KM", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLM honeypot: Interactive honeypot systems using LLMs."},
        {"key": "UWXPDZ9Z", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "GenDFIR: Cyber incident timeline analysis using RAG and LLMs."},
        {"key": "APHACZZE", "decision": "EXCLUDE", "reason_code": "EC2", "reason_text": "Investigating Bayesian spam filters (not LLM detection) against LLM-modified spam."},
        {"key": "IZHQHK6A", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Cyber attack prediction in IoT networks using LLMs (GPT/BERT)."},
        {"key": "JJEVRNR3", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "SPICED: Hardware Trojan/Bug detection using LLM-enhanced detection."},
        {"key": "N6MAEUAZ", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Survey: Transformers and LLMs for efficient IDS."},
        {"key": "4JE396MU", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Explainable network intrusion detection using LLMs."},
        {"key": "AEZ4ZPI3", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "CIDER: Detecting jailbreaking in MLLMs (Cross-modality information check)."},
        {"key": "Q27TK92F", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Anomaly detection in computational workflows using LLMs."}
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
