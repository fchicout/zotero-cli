import concurrent.futures
import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz
from tqdm import tqdm

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem


@dataclass
class AuditReport:
    total_items: int = 0
    items_missing_id: List[ZoteroItem] = field(default_factory=list)
    items_missing_title: List[ZoteroItem] = field(default_factory=list)
    items_missing_abstract: List[ZoteroItem] = field(default_factory=list)
    items_missing_pdf: List[ZoteroItem] = field(default_factory=list)
    items_missing_note: List[ZoteroItem] = field(default_factory=list)


class CollectionAuditor:
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def audit_collection(self, collection_name: str) -> Optional[AuditReport]:
        collection_id = self.gateway.get_collection_id_by_name(collection_name)
        if not collection_id:
            collection_id = (
                collection_name if self.gateway.get_collection(collection_name) else None
            )

        if not collection_id:
            print(f"Collection '{collection_name}' not found.")
            return None

        report = AuditReport()
        items_to_check_children = []

        print(f"Auditing collection: {collection_name}")
        
        # 1. Fetch items (Sequential but fast iteration)
        items_iter = self.gateway.get_items_in_collection(collection_id, top_only=True)
        
        for item in tqdm(items_iter, desc="Fetching Items", unit=" item"):
            report.total_items += 1
            if not item.has_identifier():
                report.items_missing_id.append(item)
            if not item.title:
                report.items_missing_title.append(item)
            if not item.abstract:
                report.items_missing_abstract.append(item)
            items_to_check_children.append(item)

        # 2. Check children in PARALLEL (Já existia, mantido)
        if items_to_check_children:
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_item = {
                    executor.submit(self._audit_children, item.key): item
                    for item in items_to_check_children
                }

                for future in tqdm(
                    concurrent.futures.as_completed(future_to_item), 
                    total=len(items_to_check_children), 
                    desc="Checking Children", 
                    unit=" item"
                ):
                    item = future_to_item[future]
                    try:
                        has_pdf, has_note = future.result()
                        if not has_pdf:
                            report.items_missing_pdf.append(item)
                        if not has_note:
                            report.items_missing_note.append(item)
                    except Exception as exc:
                        tqdm.write(f"Error checking children for item {item.key}: {exc}")

        return report

    def enrich_from_csv(
        self,
        csv_path: str,
        reviewer: str,
        dry_run: bool = True,
        force: bool = False,
        phase: str = "title_abstract",
        max_workers: int = 10  # Novo parâmetro para controlar paralelismo
    ) -> Dict[str, Any]:
        """
        Retroactive SDB Enrichment from CSV (Parallelized Write).
        """
        # 1. Load CSV
        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return {"error": str(e)}

        if not rows:
            return {"total_rows": 0, "matched": 0, "unmatched": [], "updated": 0, "created": 0, "skipped": 0}

        # 2. Cache Library
        print("Caching library items for matching...")
        from zotero_cli.core.models import ZoteroQuery

        raw_iter = self.gateway.search_items(ZoteroQuery())
        all_items = []
        for item in tqdm(raw_iter, desc="Downloading Library", unit=" items"):
            all_items.append(item)

        print("Building index maps...")
        items_by_key = {i.key: i for i in all_items}
        items_by_doi = {self._normalize_doi(i.doi): i for i in all_items if i.doi}
        items_by_title = {self._normalize_title(i.title): i for i in all_items if i.title}

        results = {
            "total_rows": len(rows),
            "matched": 0, "unmatched": [], "updated": 0, "created": 0, "skipped": 0
        }

        # Lista de tarefas para execução paralela depois do loop
        # Formato: (item_key, reviewer, phase, payload)
        tasks_to_process: List[Tuple[str, str, str, dict]] = []

        # 3. Matching Phase (CPU Bound - Rápido, roda sequencial)
        print(f"Matching {len(rows)} CSV rows...")
        for row in tqdm(rows, desc="Matching", unit=" row"):
            item = self._find_item_cascade(
                row, items_by_key, items_by_doi, items_by_title, all_items
            )

            if not item:
                title = row.get("Title") or row.get("title") or "Unknown"
                results["unmatched"].append(title)
                continue

            results["matched"] += 1
            sdb_payload = self._build_sdb_payload(row, reviewer, phase)

            if dry_run:
                # No dry-run, apenas imprimimos (não agendamos tarefa)
                # tqdm.write para não quebrar a barra
                # tqdm.write(f"[DRY] {item.key} | {(item.title or '')[:30]}...") 
                results["skipped"] += 1
                continue
            
            if not force:
                results["skipped"] += 1
                continue

            # Se chegamos aqui, vamos agendar para execução paralela
            tasks_to_process.append((item.key, reviewer, phase, sdb_payload))

        # 4. Writing Phase (I/O Bound - Lento, roda PARALELO)
        if tasks_to_process:
            print(f"Writing updates to Zotero ({max_workers} threads)...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submete todas as tarefas
                future_to_key = {
                    executor.submit(self._inject_sdb_note, *task): task[0] 
                    for task in tasks_to_process
                }

                # Processa conforme completam
                for future in tqdm(
                    concurrent.futures.as_completed(future_to_key),
                    total=len(tasks_to_process),
                    desc="Uploading Notes",
                    unit=" update"
                ):
                    try:
                        action = future.result()
                        if action == "updated":
                            results["updated"] += 1
                        elif action == "created":
                            results["created"] += 1
                        else:
                            results["skipped"] += 1
                    except Exception as exc:
                        key = future_to_key[future]
                        tqdm.write(f"Error updating item {key}: {exc}")
        
        return results

    # ... (O restante dos métodos _find_item_cascade, _build_sdb_payload, 
    # _inject_sdb_note, etc. permanecem iguais) ...
    
    def _find_item_cascade(self, row, by_key, by_doi, by_title, all_items):
        # (Mantém igual ao seu código original)
        key = row.get("key") or row.get("zotero_key")
        if key and key in by_key: return by_key[key]

        doi = row.get("DOI") or row.get("doi")
        if doi:
            norm_doi = self._normalize_doi(doi)
            if norm_doi in by_doi: return by_doi[norm_doi]

        title = row.get("Title") or row.get("title")
        if title:
            norm_title = self._normalize_title(title)
            if norm_title in by_title: return by_title[norm_title]
            
            # Fuzzy match (Pode ser lento se a lista for gigante, mas ok aqui)
            for item in all_items:
                if not item.title: continue
                # Otimização simples: checar tamanho antes do fuzz
                if abs(len(norm_title) - len(item.title)) > 50: continue 
                
                score = fuzz.ratio(norm_title, self._normalize_title(item.title))
                if score >= 95: return item
        return None

    def _build_sdb_payload(self, row, reviewer, phase):
        # (Mantém igual ao seu código original)
        status = row.get("Status") or row.get("Decision") or row.get("decision", "")
        status = status.lower()
        decision = "accepted" if "include" in status else ("rejected" if "exclude" in status else "unknown")
        reason_code = row.get("Reason") or row.get("reason_code") or ""
        reason_text = row.get("Comment") or row.get("reason_text") or row.get("comment", "")
        evidence = row.get("Evidence") or row.get("evidence") or ""

        return {
            "audit_version": "1.2",
            "decision": decision,
            "reason_code": [c.strip() for c in reason_code.split(",")] if reason_code else [],
            "reason_text": reason_text,
            "evidence": evidence,
            "persona": reviewer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "zotero-cli",
            "phase": phase,
            "action": "screening_decision",
        }

    def _inject_sdb_note(self, item_key: str, reviewer: str, phase: str, payload: dict) -> str:
        # (Mantém igual ao seu código original)
        children = self.gateway.get_item_children(item_key)
        existing_note_key = None
        existing_version = 0

        for child in children:
            data = child.get("data", child)
            if data.get("itemType") == "note":
                content = data.get("note", "")
                if "audit_version" in content and f'"persona": "{reviewer}"' in content and f'"phase": "{phase}"' in content:
                    existing_note_key = child.get("key") or data.get("key")
                    existing_version = int(child.get("version") or data.get("version") or 0)
                    break

        note_content = f"<div>{json.dumps(payload, indent=2)}</div>"

        if existing_note_key:
            success = self.gateway.update_note(existing_note_key, existing_version, note_content)
            return "updated" if success else "error"
        else:
            success = self.gateway.create_note(item_key, note_content)
            return "created" if success else "error"

    def _audit_children(self, item_key: str) -> tuple[bool, bool]:
        # (Mantém igual ao seu código original)
        children = self.gateway.get_item_children(item_key)
        has_pdf = False
        has_note = False
        for child in children:
            data = child.get("data", {})
            item_type = data.get("itemType")
            if item_type == "attachment" and data.get("linkMode") == "imported_file" and data.get("filename", "").lower().endswith(".pdf"):
                has_pdf = True
            if item_type == "note":
                note_text = data.get("note", "")
                if "zotero-cli" in note_text and '"decision"' in note_text:
                    has_note = True
        return has_pdf, has_note

    def _normalize_doi(self, doi: Optional[str]) -> str:
        if not doi: return ""
        doi = doi.strip().lower()
        for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
            if doi.startswith(prefix):
                doi = doi[len(prefix) :]
        return doi

    def _normalize_title(self, title: Optional[str]) -> str:
        if not title: return ""
        title = re.sub(r"[^\w\s]", "", title.lower())
        return " ".join(title.split())