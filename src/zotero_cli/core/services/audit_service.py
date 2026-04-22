import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.slr.csv_inbound import CSVInboundService
from zotero_cli.core.services.slr.integrity import AuditReport, IntegrityService
from zotero_cli.core.services.slr.snapshot import SnapshotService


class CollectionAuditor:
    """
    DEPRECATED: Use IntegrityService, SnapshotService, or CSVInboundService directly.
    Maintained for backward compatibility during Phase B.
    """
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway
        self.integrity = IntegrityService(gateway)
        self.snapshot = SnapshotService()
        self.csv_inbound = CSVInboundService(gateway)

    def audit_collection(self, collection_name: str) -> Optional[AuditReport]:
        return self.integrity.audit_collection(collection_name)

    def detect_shifts(self, snapshot_old: List[dict], snapshot_new: List[dict]) -> List[dict]:
        return self.snapshot.detect_shifts(snapshot_old, snapshot_new)

    def enrich_from_csv(self, csv_path: str, **kwargs) -> Dict[str, Any]:
        return self.csv_inbound.enrich_from_csv(csv_path=csv_path, **kwargs)

    def _audit_children(self, item_key: str) -> tuple[bool, bool]:
        """Backward compatibility for tests."""
        return self.integrity._audit_children(item_key)


class AuditService:
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def audit_manuscript(self, path: Path) -> Dict[str, Any]:
        """
        Audits a LaTeX manuscript for citations and verifies them against the Zotero library and SDB.
        """
        citations = self._get_citations_recursive(path)

        items_report: Dict[str, Dict[str, Any]] = {}
        report = {
            "path": str(path),
            "total_citations": len(citations),
            "items": items_report,  # key -> {exists: bool, screened: bool, decision: str, title: str}
        }

        from zotero_cli.core.utils.sdb_parser import parse_sdb_note

        for key in sorted(list(citations)):
            item = self.gateway.get_item(key)
            if not item:
                items_report[key] = {"exists": False, "screened": False}
                continue

            # Check for SDB note
            children = self.gateway.get_item_children(key)
            screened = False
            decision = None

            for child in children:
                data = child.get("data", child)
                if data.get("itemType") == "note":
                    parsed = parse_sdb_note(data.get("note", ""))
                    if parsed:
                        screened = True
                        decision = parsed.get("decision")
                        break

            items_report[key] = {
                "exists": True,
                "screened": screened,
                "decision": decision,
                "title": item.title,
            }

        return report

    def _get_citations_recursive(self, latex_file: Path, visited=None) -> set:
        if visited is None:
            visited = set()

        if latex_file in visited or not latex_file.exists():
            return set()

        visited.add(latex_file)

        try:
            with open(latex_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Warning: Failed to read {latex_file}: {e}")
            return set()

        # Filter out commented lines
        content = re.sub(r"%.*", "", content)

        citations = re.findall(r"\\cite\{([^}]+)\}", content)
        unique_citations = set()
        for cite in citations:
            unique_citations.update([c.strip() for c in cite.split(",")])

        # Recursively find citations in included files (\input, \include)
        included_files = re.findall(r"\\(?:input|include)\{([^}]+)\}", content)
        for inc in included_files:
            if not inc.endswith(".tex"):
                inc += ".tex"
            inc_path = latex_file.parent / inc
            unique_citations.update(self._get_citations_recursive(inc_path, visited))

        return unique_citations
