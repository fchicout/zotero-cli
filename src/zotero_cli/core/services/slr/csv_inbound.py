import csv
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.utils.normalization import normalize_doi, normalize_title
from zotero_cli.core.zotero_item import ZoteroItem


class ItemMatcher(ABC):
    @abstractmethod
    def match(self, row: Dict[str, str], items: List[ZoteroItem], column_map: Dict[str, str]) -> Optional[ZoteroItem]:
        pass

class KeyMatcher(ItemMatcher):
    def __init__(self, items_by_key: Dict[str, ZoteroItem]):
        self.items_by_key = items_by_key

    def match(self, row: Dict[str, str], items: List[ZoteroItem], column_map: Dict[str, str]) -> Optional[ZoteroItem]:
        key_col = column_map.get("key", "Key")
        key = row.get(key_col) or row.get("key") or row.get("zotero_key")
        return self.items_by_key.get(key) if key else None

class DOIMatcher(ItemMatcher):
    def __init__(self, items_by_doi: Dict[str, ZoteroItem]):
        self.items_by_doi = items_by_doi

    def match(self, row: Dict[str, str], items: List[ZoteroItem], column_map: Dict[str, str]) -> Optional[ZoteroItem]:
        doi_col = column_map.get("doi", "DOI")
        doi = row.get(doi_col) or row.get("doi")
        if not doi:
            return None
        return self.items_by_doi.get(normalize_doi(doi))

class FuzzyTitleMatcher(ItemMatcher):
    def match(self, row: Dict[str, str], items: List[ZoteroItem], column_map: Dict[str, str]) -> Optional[ZoteroItem]:
        title_col = column_map.get("title", "Title")
        title = row.get(title_col) or row.get("title")
        if not title:
            return None

        norm_target = normalize_title(title)
        best_match = None
        best_score = 0.0

        for item in items:
            if not item.title:
                continue
            score = fuzz.ratio(norm_target, normalize_title(item.title))
            if score > best_score:
                best_score = score
                best_match = item

        return best_match if best_score >= 95 else None

class CSVInboundService:
    """
    Handles retroactive metadata enrichment from CSV files.
    """
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def enrich_from_csv(
        self,
        csv_path: str,
        reviewer: str,
        dry_run: bool = True,
        force: bool = False,
        phase: str = "title_abstract",
        column_map: Optional[Dict[str, str]] = None,
        move_to_included: Optional[str] = None,
        move_to_excluded: Optional[str] = None,
        collection_service: Optional[Any] = None,
    ) -> Dict[str, Any]:

        actual_map = {
            "key": "Key", "vote": "Vote", "reason": "Reason",
            "code": "Code", "doi": "DOI", "title": "Title",
            "comment": "Comment", "evidence": "Evidence"
        }
        if column_map:
            actual_map.update(column_map)

        rows = self._load_csv(csv_path, actual_map, column_map)
        if "error" in rows:
            return rows # type: ignore

        if not rows:
            return {"total_rows": 0, "matched": 0, "unmatched": [], "updated": 0, "created": 0, "skipped": 0}

        # Cache items and matchers
        from zotero_cli.core.models import ZoteroQuery
        all_items = list(self.gateway.search_items(ZoteroQuery()))
        matchers = [
            KeyMatcher({i.key: i for i in all_items}),
            DOIMatcher({normalize_doi(i.doi): i for i in all_items if i.doi}),
            FuzzyTitleMatcher()
        ]

        results: Dict[str, Any] = {
            "total_rows": len(rows),
            "matched": 0,
            "unmatched": [],
            "updated": 0,
            "created": 0,
            "skipped": 0,
        }

        for row in rows:
            item = self._find_item(row, all_items, matchers, actual_map)
            if not item:
                results["unmatched"].append(row.get(actual_map.get("title", "Title")) or "Unknown")
                continue

            results["matched"] += 1
            payload = self._build_sdb_payload(row, reviewer, phase, actual_map)

            if dry_run or not force:
                print(f"[DRY RUN] Match: {item.key} | {(item.title or '')[:40]}...")
                results["skipped"] += 1
                continue

            action = self._inject_sdb_note(item.key, reviewer, phase, payload)
            # Use results.get or explicit keys to avoid mypy object error
            if action == "update":
                results["updated"] += 1
            elif action == "create":
                results["created"] += 1
            else:
                results["skipped"] += 1

            if action != "error":
                self._handle_movement(
                    item.key,
                    payload["decision"],
                    move_to_included,
                    move_to_excluded,
                    collection_service,
                )

        return results

    def _load_csv(self, path: str, actual_map: Dict[str, str], user_map: Optional[Dict[str, str]]) -> Any:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames or []
                if user_map:
                    missing = [v for k, v in user_map.items() if v not in header]
                    if missing:
                        return {"error": f"Missing columns: {', '.join(missing)}"}
                return list(reader)
        except Exception as e:
            return {"error": str(e)}

    def _find_item(self, row: Dict[str, str], items: List[ZoteroItem], matchers: List[ItemMatcher], col_map: Dict[str, str]) -> Optional[ZoteroItem]:
        for matcher in matchers:
            item = matcher.match(row, items, col_map)
            if item:
                return item
        return None

    def _build_sdb_payload(self, row: Dict[str, str], reviewer: str, phase: str, col_map: Dict[str, str]) -> dict:
        # Priority: 1. User mapped 'vote' column, 2. fallback to row keys like 'status' or 'vote'
        status_val = row.get(col_map.get("vote", "Vote"))
        if status_val is None:
            status_val = row.get("status") or row.get("Vote") or ""
        
        status = str(status_val).lower()
        if "include" in status or "accept" in status:
            decision = "accepted"
        elif "exclude" in status or "reject" in status:
            decision = "rejected"
        else:
            decision = "unknown"

        return {
            "audit_version": "1.2",
            "decision": decision,
            "reason_code": [c.strip() for c in (row.get(col_map.get("code", "Code")) or "").split(",")]
            if row.get(col_map.get("code", "Code"))
            else [],
            "reason_text": row.get(col_map.get("reason", "Reason")) or row.get("Reason", ""),
            "evidence": row.get(col_map.get("evidence", "Evidence")) or row.get("evidence", ""),
            "persona": reviewer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "zotero-cli",
            "phase": phase,
            "action": "screening_decision",
        }
    def _inject_sdb_note(self, item_key: str, reviewer: str, phase: str, payload: dict) -> str:
        children = self.gateway.get_item_children(item_key)
        note_key, version = None, 0
        for child in children:
            data = child.get("data", child)
            if data.get("itemType") == "note":
                content = data.get("note", "")
                if "audit_version" in content and f'"persona": "{reviewer}"' in content and f'"phase": "{phase}"' in content:
                    note_key, version = child.get("key") or data.get("key"), int(child.get("version") or data.get("version") or 0)
                    break

        content = f"<div>{json.dumps(payload, indent=2)}</div>"
        if note_key:
            return "update" if self.gateway.update_note(note_key, version, content) else "error"
        return "create" if self.gateway.create_note(item_key, content) else "error"

    def _handle_movement(self, key: str, decision: str, inc: Optional[str], excl: Optional[str], svc: Any):
        target = inc if decision == "accepted" else (excl if decision == "rejected" else None)
        if target and svc:
            svc.move_item(source_col_name=None, dest_col_name=target, identifier=key)
