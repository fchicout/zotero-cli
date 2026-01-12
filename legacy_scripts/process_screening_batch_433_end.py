
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
        {"key": "8QSKC8PF", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "DemonAgent: Backdoor attack on LLM agents (Attack)."},
        {"key": "3AW7R739", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "G-safeguard: Anomaly detection on LLM-based multi-agent systems."},
        {"key": "9PNBBKZN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "APT-LLM: APT detection using BERT/RoBERTa embeddings."},
        {"key": "K3AI76D4", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Hybrid LLM-enhanced intrusion detection (GPT-2) for zero-day threats."},
        {"key": "4T6M24C6", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Vulnerability assessment of LLM agent deployment (Risk analysis)."},
        {"key": "86BRKDDJ", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "CyberRAG: Agentic RAG tool for cyber attack classification and reporting."},
        {"key": "GG634F5A", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Adaptive Linguistic Prompting: Phishing webpage detection using MLLMs."},
        {"key": "AG33AK8A", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Generative AI for vulnerability detection in 6G networks."},
        {"key": "VE2HAM6V", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "JsDeObsBench: Benchmarking LLMs for JavaScript deobfuscation (Analysis)."},
        {"key": "C5TQZ6KA", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "PhishingHook: Phishing detection in smart contracts using Language Models."},
        {"key": "UDP2R36C", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "PDF malware analysis via intermediate representation and language model."},
        {"key": "VIJKD8CN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLM-powered intent-based categorization of phishing emails."},
        {"key": "F9JT4AFB", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Detecting hard-coded credentials using LLMs (GPT)."},
        {"key": "C45XQX4D", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "SmartHome-bench: Video anomaly detection benchmark using MLLMs."},
        {"key": "44RDE9EN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Anomaly detection in multi-cloud monitoring based on LLM."},
        {"key": "ZDJQ2SU8", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Automated vulnerability repair using CodeBERT/CodeT5 (Response)."},
        {"key": "263Z6QMB", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "TraCR-TMF: LLM-based threat modeling framework for transportation CPS."},
        {"key": "5WUVTAAV", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Misinformation generation (Attack)."},
        {"key": "CUVC2MKI", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "GUARD: Backdoor detection in code generation (Detection of attacks on AI)."},
        {"key": "349QW59Z", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "TrojanStego: Privacy leakage attack."},
        {"key": "DKUPW84U", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Systematic review: LLM-driven APT detection."},
        {"key": "FA9UQ5EG", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "RRTL: Red teaming (Threat detection) of reasoning LLMs."},
        {"key": "FKVDTKWT", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Propaganda detection using LLMs (GPT-4/Claude)."},
        {"key": "RZUV9INN", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Impact assessment of phishing/quishing (Not detection proposal)."},
        {"key": "H7FP5D3Q", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Threat-actor attribution/TTP identification using LLMs."},
        {"key": "H9DXE5TA", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "LATENT: Trojan insertion framework (Attack)."},
        {"key": "2V8HXCCN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLM-driven IoT security assistant (Detection/Mitigation support)."},
        {"key": "6SPEHDCU", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Identification of attack techniques in CTI reports using LLMs."},
        {"key": "T2ZPRXUH", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "CONFIGSCAN: Detecting malicious configurations in model repositories."},
        {"key": "FVF4N28T", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Leveraging LLM to strengthen XSS detection (Data Augmentation)."},
        {"key": "5Q8ZC67A", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Survey of malicious URL detection."},
        {"key": "2F5DQ99F", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Cloud network traffic monitoring and anomaly detection based on LLMs."},
        {"key": "TZNCNVXT", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Evaluating LLM robustness for malware detection against obfuscation."},
        {"key": "WFBZ3K8Q", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Attack on LLM watermarks (Security OF AI)."},
        {"key": "ZEAQFEQ8", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Longitudinal analysis of APTs using LLM-based search."},
        {"key": "G37UND2E", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Agentic AI for explainable cyberthreat mitigation in IoEV."},
        {"key": "KGUQTW89", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "EverTracer: Hunting stolen LLMs (Model theft detection)."},
        {"key": "HQU7PPQI", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "FakeSV-VLM: Detecting fake short-video news using VLMs."},
        {"key": "N29K8CJ5", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "High-quality malcode generation for IDS training (Data Augmentation)."},
        {"key": "B5PSZBVG", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "MalLoc: Fine-grained Android malicious payload localization via LLMs."},
        {"key": "7IGWTFG9", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "IPIGuard: Defense against indirect prompt injection (Detection/Prevention)."},
        {"key": "M7ADPTXG", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "GenAI-based anomaly detection for energy management systems."},
        {"key": "CPTW5ZE5", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Role of LLMs in blockchain voting anomaly detection."},
        {"key": "GFX3KR5W", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "DBOM: Proactive modeling for backdoor defense using VLMs."},
        {"key": "S34RBDQA", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "LLM-based attacks on voice phishing classifiers (Attack)."},
        {"key": "JCKWGNR7", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "eX-NIDS: Explainable network intrusion detection using LLMs."},
        {"key": "4VKCCWJA", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Multi-stage prompt inference attacks (Attack)."},
        {"key": "RGDQ7568", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "PhishIntentionLLM: Uncovering phishing intentions using RAG/LLMs."},
        {"key": "8H9BZEFW", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "PiMRef: Detecting spear phishing with knowledge base invariants (and LLM threat context)."},
        {"key": "AKDMIVKN", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Survey: LLMs in cybersecurity."},
        {"key": "3MMQRH5G", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Prompt injection 2.0 (Threat analysis)."},
        {"key": "TKCEKZ4Q", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "SHIELD: LLM-aided framework for host-based intrusion detection."},
        {"key": "7AGWUVZ3", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "REAL-IoT: LLM-based filtering for GNN intrusion detection robustness."},
        {"key": "GKWNWXQ3", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "ExCyTIn-bench: Evaluating LLM agents on cyber threat investigation."},
        {"key": "346F2HVN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Inject-and-detect: Detecting LLM-generated reviews (Imposter detection)."},
        {"key": "X8TT2XB6", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Odysseus: Jailbreaking commercial multimodal LLMs (Attack)."},
        {"key": "59TWVGZR", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Generation of rules for document forgery detection using LLMs."},
        {"key": "J9SF3EVI", "decision": "EXCLUDE", "reason_code": "EC2", "reason_text": "Efficient jailbreak mitigation using Linear SVM (Not LLM-based detection)."},
        {"key": "MATFKQP3", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Automated red-teaming framework for LLM security assessment."},
        {"key": "STJV7FI9", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "XG-Guard: Safeguarding LLM multi-agent systems via graph anomaly detection."},
        {"key": "36T3WCST", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Bilevel optimization for covert memory tampering (Attack)."},
        {"key": "93IIS5NV", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Cisco AI security and safety framework report."},
        {"key": "SGSC3AHM", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "RCS: Rethinking jailbreak detection of LVLMs (Internal representation analysis)."},
        {"key": "N6I6I7N8", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "TriDF: Benchmark for interpretable DeepFake detection using MLLMs."},
        {"key": "BC2D8JN6", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLMPEA: LLM-based framework to detect phishing email attacks."},
        {"key": "73WRJSWV", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "SCOUT: Defense against data poisoning using saliency analysis (in LMs)."},
        {"key": "T5M7HMNP", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "MINES: Explainable anomaly detection through web API invariant inference (using LLM)."},
        {"key": "QFWJ4TWE", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Patronus: Identifying and mitigating transferable backdoors in PLMs."},
        {"key": "FHSMJZK7", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Securing MCP: LLM-on-LLM semantic vetting for tool poisoning."},
        {"key": "A6T5A2QR", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "AgenticCyber: GenAI-powered multi-agent system for multimodal threat detection."},
        {"key": "XWCMNMDH", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "ARGUS: Defending against multimodal indirect prompt injection (Detection/Steering)."},
        {"key": "AFN5832P", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "WebShell family classification: Data augmentation with LLMs."},
        {"key": "XEAKG4UQ", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "SoK: Causality analysis framework for LLM security."},
        {"key": "69ISP2JW", "decision": "EXCLUDE", "reason_code": "EC2", "reason_text": "MICRYSCOPE: Cryptographic misuse detection (Traditional Static Analysis/Taint)."},
        {"key": "5MWT2NRE", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "MAAG: Multi-Agent Adaptive Guard for jailbreak detection."},
        {"key": "8NP9HCGF", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "AGENTSAFE: Governance/Anomaly detection in agentic AI."},
        {"key": "PR5AX6FK", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "BiasDef: Post-retrieval filtering defense against bias injection in RAG."},
        {"key": "8SGUZWZ7", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "TrojanLoC: LLM-based framework for RTL trojan localization."},
        {"key": "7328M34Z", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Labeled email dataset for phishing detection (LLM benchmarking)."},
        {"key": "2STS3I94", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Agent-based defense against jailbreak exploits."},
        {"key": "Q73H95CD", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "IoT intrusion reasoning using IDS and LLMs at the edge."},
        {"key": "56DIJ6EI", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "ReCoVAD: Video anomaly detection with large pre-trained models."},
        {"key": "59VNDBTC", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "MultiPriv: Privacy reasoning risk benchmark (Risk assessment)."},
        {"key": "5ZKG4JG3", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LLM-powered agentic red teaming (Vulnerability detection)."},
        {"key": "W9J7TFNB", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "AquaSentinel: Anomaly detection in water pipelines via MoE-LLM agents."},
        {"key": "5JQBJW6I", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "SLMs for phishing website detection."},
        {"key": "PTH3VFEJ", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Securing AI agents: Anomaly detection and guardrails."},
        {"key": "EAKPIJKK", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "AdapT-Bench: Benchmarking MLLMs for phishing detection."},
        {"key": "TP888DM8", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "BGPShield: BGP anomaly detection using LLM embeddings."},
        {"key": "83SFUQ6I", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "MalRAG: Retrieval-augmented LLM for malicious traffic identification."},
        {"key": "QWEBP3AZ", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LogPurge: Log data purification for anomaly detection via LLMs."},
        {"key": "UK64MS7T", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "AutoMalDesc: Script analysis for cyber threat research using LLMs."},
        {"key": "BG8BH59C", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Backdoor detection based on attention similarity in LLMs."},
        {"key": "7D5HK9JI", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Privacy-preserving prompt injection detection using federated learning/NLP."},
        {"key": "C3FWFZK6", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LASiR: Detecting signature replay vulnerabilities in smart contracts using LLMs."},
        {"key": "KV9Q93SV", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Actionable cybersecurity notifications for smart homes using LLMs."},
        {"key": "NZ6C2R8H", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Leveraging LLMs for high-level threat understanding from security logs."},
        {"key": "4E9SGTXU", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "MASK: Privacy-preserving phone scam detection using LLMs."},
        {"key": "5IBQZU9S", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "OCR-APT: Reconstructing APT stories from audit logs using LLMs."},
        {"key": "52WRRWK5", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Steering web agent preferences (Attack)."},
        {"key": "JXH4T8KD", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Evaluating efficacy of LLMs in identifying phishing attempts."},
        {"key": "7RKDSGJD", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Explainable transformer-based model (DistilBERT) for phishing email detection."},
        {"key": "A2XPZ3EN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "GradSafe: Detecting jailbreak prompts via gradient analysis."},
        {"key": "S4Z4K3TC", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Stealthy attack on LLM based recommendation."},
        {"key": "ZBDSPQRF", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Cyberbullying detection using LLMs (BERT/RoBERTa)."},
        {"key": "8UQQIACX", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "HATEGUARD: Moderating online hate with CoT in LLMs."},
        {"key": "WEA6BGJ5", "decision": "EXCLUDE", "reason_code": "EC4", "reason_text": "Survey on LLM security and privacy."},
        {"key": "H6D3J4NC", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Nexus: Fine-tuning Arabic language models for propaganda detection."},
        {"key": "BJIFQJTN", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "IPSDM: Detecting phishing and spam using BERT."},
        {"key": "BGU2TJVH", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "LogGPT: Log anomaly detection via GPT."},
        {"key": "NIBX37BW", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "REEF: Collecting real-world vulnerabilities and fixes using Neural LMs."},
        {"key": "95SMP3AQ", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "KDDT: Digital twin for anomaly detection using Language Models."},
        {"key": "DUANZ742", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "shelLM: Generative honeypots using LLMs."},
        {"key": "BTC69EJX", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Detecting fake and LLM-generated LinkedIn profiles using BERT/RoBERTa."},
        {"key": "Z8VIWW98", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Flow-based NIDS using BERT."},
        {"key": "32JCAK6A", "decision": "EXCLUDE", "reason_code": "EC1", "reason_text": "Urban science research (Not cybersecurity threat detection)."},
        {"key": "QEWEEQ4B", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Masked language model based textual adversarial example detection."},
        {"key": "FTHTN3CU", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "CAN-BERT: CAN bus intrusion detection using BERT."},
        {"key": "C3V7DVAX", "decision": "INCLUDE", "reason_code": "IC1, IC2", "reason_text": "Log anomaly detection using Pre-trained Language Models."}
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
