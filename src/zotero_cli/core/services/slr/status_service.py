from dataclasses import dataclass, field
from typing import Dict, List, Optional

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.slr.orchestrator import SLROrchestrator
from zotero_cli.core.utils.sdb_parser import parse_sdb_note


@dataclass
class PhaseStats:
    accepted: int = 0
    rejected: int = 0
    pending: int = 0

@dataclass
class SLRStatus:
    source_name: str
    source_key: str
    total_in_root: int = 0
    phases: Dict[str, PhaseStats] = field(default_factory=dict)

    @property
    def total_unique(self) -> int:
        """Sum of papers in root plus all papers accepted in subsequent phases."""
        phase_sum = sum(p.accepted for p in self.phases.values())
        return self.total_in_root + phase_sum

class SLRStatusService:
    """
    Orchestrates SLR status reporting by analyzing the physical displacement
    of items between phase folders and their internal SDB metadata.
    """

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway
        self.orchestrator = SLROrchestrator(gateway)

    def get_slr_status(self) -> List[SLRStatus]:
        all_collections = self.gateway.get_all_collections()
        raw_collections = [
            c for c in all_collections
            if c["data"]["name"].startswith("raw_") and not c["data"].get("parentCollection")
        ]

        results = []
        for raw_col in raw_collections:
            source_key = raw_col["key"]
            source_name = raw_col["data"]["name"]

            # Ensure hierarchy and get keys via orchestrator
            phase_map = self.orchestrator.ensure_slr_hierarchy(source_key, all_collections)

            status = SLRStatus(source_name=source_name, source_key=source_key)

            # The "Root" folder is the source for the first phase
            source_for_next_phase = source_key

            for phase_cfg in self.orchestrator.PHASE_FLOW:
                phase_id = phase_cfg["id"]
                folder_name = phase_cfg["folder"]
                folder_key = phase_map.get(folder_name)

                stats = PhaseStats()

                # 1. Accepted: Count papers actually in the target folder
                if folder_key:
                    folder_items = list(self.gateway.get_items_in_collection(folder_key))
                    stats.accepted = len([i for i in folder_items if i.raw_data["data"].get("itemType") not in ["attachment", "note"]])

                # 2. Rejected & Pending: Count papers in the SOURCE folder looking for notes of THIS phase
                source_items = list(self.gateway.get_items_in_collection(source_for_next_phase))
                source_papers = [i for i in source_items if i.raw_data["data"].get("itemType") not in ["attachment", "note"]]

                if source_for_next_phase == source_key:
                    status.total_in_root = len(source_papers)

                for paper in source_papers:
                    children = self.gateway.get_item_children(paper.key)
                    decision = self._get_phase_decision(children, phase_id)

                    if decision == "rejected":
                        stats.rejected += 1
                    elif decision is None:
                        # No note for this phase in the source folder means it's pending evaluation
                        stats.pending += 1

                status.phases[phase_id] = stats

                # The current folder becomes the source for the next phase in the loop
                source_for_next_phase = folder_key

            results.append(status)

        return results

    def _get_phase_decision(self, children: List[dict], phase_id: str) -> Optional[str]:
        for child in children:
            if child.get("data", {}).get("itemType") == "note":
                parsed = parse_sdb_note(child.get("data", {}).get("note", ""))
                if parsed and parsed.get("phase") == phase_id:
                    return parsed.get("decision")
        return None
