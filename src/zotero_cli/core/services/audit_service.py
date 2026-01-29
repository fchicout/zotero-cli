import concurrent.futures
import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz

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
            # Maybe it's already a key
            collection_id = (
                collection_name if self.gateway.get_collection(collection_name) else None
            )

        if not collection_id:
            print(f"Collection '{collection_name}' not found.")
            return None

        report = AuditReport()
        items_to_check_children = []

        # 1. Fetch items and perform local checks (Top-level only)
        for item in self.gateway.get_items_in_collection(collection_id, top_only=True):
            report.total_items += 1

            if not item.has_identifier():
                report.items_missing_id.append(item)
            if not item.title:
                report.items_missing_title.append(item)
            if not item.abstract:
                report.items_missing_abstract.append(item)

            items_to_check_children.append(item)

        # 2. Check for children (PDFs and Notes) in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_item = {
                executor.submit(self._audit_children, item.key): item
                for item in items_to_check_children
            }

            for future in concurrent.futures.as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    has_pdf, has_note = future.result()
                    if not has_pdf:
                        report.items_missing_pdf.append(item)
                    if not has_note:
                        report.items_missing_note.append(item)
                except Exception as exc:
                    print(f"Error checking children for item {item.key}: {exc}")

        return report

    def detect_shifts(self, snapshot_old: List[dict], snapshot_new: List[dict]) -> List[dict]:
        """
        Compares two snapshots (lists of item dicts) and returns items that changed collections.
        """
        map_old = {i["key"]: set(i.get("collections", [])) for i in snapshot_old}
        map_new = {i["key"]: set(i.get("collections", [])) for i in snapshot_new}

        shifts = []

        # 1. Detect Changes and Additions
        for key, cols_new in map_new.items():
            if key in map_old:
                cols_old = map_old[key]
                if cols_new != cols_old:
                    shifts.append(
                        {
                            "key": key,
                            "title": next(
                                (i["title"] for i in snapshot_new if i["key"] == key), "Unknown"
                            ),
                            "from": list(cols_old),
                            "to": list(cols_new),
                        }
                    )
            else:
                # Newly added item
                shifts.append(
                    {
                        "key": key,
                        "title": next(
                            (i["title"] for i in snapshot_new if i["key"] == key), "Unknown"
                        ),
                        "from": [],
                        "to": list(cols_new),
                    }
                )

        # 2. Detect Deletions / Removals
        for key, cols_old in map_old.items():
            if key not in map_new:
                shifts.append(
                    {
                        "key": key,
                        "title": next(
                            (i["title"] for i in snapshot_old if i["key"] == key), "Unknown"
                        ),
                        "from": list(cols_old),
                        "to": [],
                    }
                )

        return shifts

    def enrich_from_csv(
        self,
        csv_path: str,
        reviewer: str,
        dry_run: bool = True,
        force: bool = False,
        phase: str = "title_abstract",
        column_map: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Retroactive SDB Enrichment from CSV.
        """
        # Default mapping
        default_map = {
            "key": "Key",
            "vote": "Vote",
            "reason": "Reason",
            "code": "Code",
            "doi": "DOI",
            "title": "Title",
            "comment": "Comment",
            "evidence": "Evidence",
        }
        actual_map = default_map.copy()
        if column_map:
            actual_map.update(column_map)

        # 1. Load CSV
        rows: List[Dict[str, str]] = []
        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames or []
                
                # Validation: Check if required mapped columns exist in header
                # We prioritize mapping, then fallback to defaults if not mapped.
                # However, for 'key', 'doi', 'title' we search multiple fields usually.
                # Let's validate the specific fields used in _build_sdb_payload and cascades.
                missing = []
                for internal_key, csv_col in actual_map.items():
                    # If user provided a mapping, it MUST exist.
                    # If using default, we are more lenient (cascading check later).
                    if column_map and internal_key in column_map and csv_col not in header:
                        missing.append(csv_col)
                
                if missing:
                    return {"error": f"Missing required columns in CSV: {', '.join(missing)}"}

                rows = list(reader)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return {"error": str(e)}

        if not rows:
            return {
                "total_rows": 0,
                "matched": 0,
                "unmatched": [],
                "updated": 0,
                "created": 0,
                "skipped": 0,
            }

        # 2. Cache Library Items for Matching
        print("Caching library items for matching...")
        from zotero_cli.core.models import ZoteroQuery

        all_items = list(self.gateway.search_items(ZoteroQuery()))

        # Build lookup maps
        items_by_key = {i.key: i for i in all_items}
        items_by_doi = {self._normalize_doi(i.doi): i for i in all_items if i.doi}
        # Title map for exact matches, fuzzy used later
        items_by_title = {self._normalize_title(i.title): i for i in all_items if i.title}

        results: Dict[str, Any] = {
            "total_rows": len(rows),
            "matched": 0,
            "unmatched": [],
            "updated": 0,
            "created": 0,
            "skipped": 0,
        }

        for row in rows:
            item = self._find_item_cascade(
                row, items_by_key, items_by_doi, items_by_title, all_items, actual_map
            )

            if not item:
                # Use mapped title or fallback
                title_col = actual_map.get("title", "Title")
                title = row.get(title_col) or row.get("title") or "Unknown"
                results["unmatched"].append(title)
                continue

            results["matched"] += 1

            # 3. Construct SDB Payload
            sdb_payload = self._build_sdb_payload(row, reviewer, phase, actual_map)

            if dry_run:
                print(
                    f"[DRY RUN] Match: {item.key} | {(item.title or '')[:40]}... | {reviewer} | {phase}"
                )
                results["skipped"] += 1
                continue

            if not force:
                results["skipped"] += 1
                continue

            # 4. Inject/Update Note
            action = self._inject_sdb_note(item.key, reviewer, phase, sdb_payload)
            if action == "updated":
                results["updated"] += 1
            elif action == "created":
                results["created"] += 1
            else:
                results["skipped"] += 1

        return results

    def _find_item_cascade(
        self,
        row: Dict[str, str],
        by_key: Dict[str, ZoteroItem],
        by_doi: Dict[str, ZoteroItem],
        by_title: Dict[str, ZoteroItem],
        all_items: List[ZoteroItem],
        column_map: Dict[str, str],
    ) -> Optional[ZoteroItem]:
        # 1. Key
        key_col = column_map.get("key", "Key")
        key = row.get(key_col) or row.get("key") or row.get("zotero_key")
        if key and key in by_key:
            return by_key[key]

        # 2. DOI
        doi_col = column_map.get("doi", "DOI")
        doi = row.get(doi_col) or row.get("doi")
        if doi:
            norm_doi = self._normalize_doi(doi)
            if norm_doi in by_doi:
                return by_doi[norm_doi]

        # 3. Title (Exact)
        title_col = column_map.get("title", "Title")
        title = row.get(title_col) or row.get("title")
        if title:
            norm_title = self._normalize_title(title)
            if norm_title in by_title:
                return by_title[norm_title]

            # 4. Title (Fuzzy)
            # This is slow, so we only do it if Title is present
            for item in all_items:
                if not item.title:
                    continue
                score = fuzz.ratio(norm_title, self._normalize_title(item.title))
                if score >= 95:
                    return item

        return None

    def _build_sdb_payload(self, row: Dict[str, str], reviewer: str, phase: str, column_map: Dict[str, str]) -> dict:
        vote_col = column_map.get("vote", "Vote")
        status = row.get(vote_col) or row.get("Status") or row.get("Decision") or row.get("decision", "")
        status = status.lower()
        decision = (
            "accepted"
            if "include" in status
            else ("rejected" if "exclude" in status else "unknown")
        )

        reason_col = column_map.get("reason", "Reason")
        code_col = column_map.get("code", "Code")
        
        # SDB v1.2 usually uses 'reason_code' for the codes and 'reason_text' for the text.
        # We try to get them from mapped columns.
        reason_code_str = row.get(code_col) or row.get("Code") or row.get("reason_code") or ""
        reason_text = row.get(reason_col) or row.get("Reason") or row.get("Comment") or row.get("reason_text") or row.get("comment", "")
        
        evidence_col = column_map.get("evidence", "Evidence")
        evidence = row.get(evidence_col) or row.get("Evidence") or row.get("evidence") or ""

        return {
            "audit_version": "1.2",
            "decision": decision,
            "reason_code": [c.strip() for c in reason_code_str.split(",")] if reason_code_str else [],
            "reason_text": reason_text,
            "evidence": evidence,
            "persona": reviewer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "zotero-cli",
            "phase": phase,
            "action": "screening_decision",
        }

    def _inject_sdb_note(self, item_key: str, reviewer: str, phase: str, payload: dict) -> str:
        """
        Injects or updates the SDB note. Returns 'created', 'updated', or 'error'.
        """
        children = self.gateway.get_item_children(item_key)
        existing_note_key: Optional[str] = None
        existing_version: int = 0

        for child in children:
            data = child.get("data", child)
            if data.get("itemType") == "note":
                content = data.get("note", "")
                if (
                    "audit_version" in content
                    and f'"persona": "{reviewer}"' in content
                    and f'"phase": "{phase}"' in content
                ):
                    existing_note_key = child.get("key") or data.get("key")
                    # Ensure we have a version
                    existing_version = int(child.get("version") or data.get("version") or 0)
                    break

        note_content = f"<div>{json.dumps(payload, indent=2)}</div>"

        if existing_note_key:
            success = self.gateway.update_note(existing_note_key, existing_version, note_content)
            return "updated" if success else "error"
        else:
            success = self.gateway.create_note(item_key, note_content)
            return "created" if success else "error"

    def _normalize_doi(self, doi: Optional[str]) -> str:
        if not doi:
            return ""
        doi = doi.strip().lower()
        # Remove common prefixes
        for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
            if doi.startswith(prefix):
                doi = doi[len(prefix) :]
        return doi

    def _normalize_title(self, title: Optional[str]) -> str:
        if not title:
            return ""
        # Remove non-alphanumeric and extra whitespace
        import re

        title = re.sub(r"[^\w\s]", "", title.lower())
        return " ".join(title.split())

    def _audit_children(self, item_key: str) -> tuple[bool, bool]:
        """Returns (has_pdf, has_screening_note)"""
        children = self.gateway.get_item_children(item_key)
        has_pdf = False
        has_note = False

        for child in children:
            data = child.get("data", {})
            item_type = data.get("itemType")

            # Check PDF
            if (
                item_type == "attachment"
                and data.get("linkMode") == "imported_file"
                and data.get("filename", "").lower().endswith(".pdf")
            ):
                has_pdf = True

            # Check Screening Note (JSON)
            if item_type == "note":
                note_text = data.get("note", "")
                if "zotero-cli" in note_text and '"decision"' in note_text:
                    has_note = True

        return has_pdf, has_note
