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
class PendingItem:
    item_key: str
    title: str
    source_collection: str
    phase: str
    reason: str

@dataclass
class SLRStatus:
    source_name: str
    source_key: str
    tree_total: int = 0
    total_in_root: int = 0
    total_unique: int = 0
    phases: Dict[str, PhaseStats] = field(default_factory=dict)

class SLRStatusService:
    """
    Orchestrates SLR status reporting by analyzing SDB metadata (Notes)
    as the primary source of truth, with physical folder location
    defining the 'Pending' queue.
    """

    def __init__(self, gateway: ZoteroGateway, orchestrator: SLROrchestrator):
        self.gateway = gateway
        self.orchestrator = orchestrator

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

            # 1. Collect All Papers in Tree (Source + all Phase Folders)
            all_papers = self.orchestrator.get_all_papers_in_tree(source_key)
            status = SLRStatus(source_name=source_name, source_key=source_key, tree_total=len(all_papers))

            # 2. Cache All Parsed SDB Notes for these items
            item_notes = {}
            for paper in all_papers:
                children = self.gateway.get_item_children(paper.key)
                parsed_notes = []
                for child in children:
                    if child.get("data", {}).get("itemType") == "note":
                        parsed = parse_sdb_note(child.get("data", {}).get("note", ""))
                        if parsed:
                            parsed_notes.append(parsed)
                item_notes[paper.key] = parsed_notes

            # 3. Calculate Phase Stats (Note-First)
            phase_map = self.orchestrator.ensure_slr_hierarchy(source_key, all_collections)

            # Start with Root as the initial queue
            current_queue_key = source_key

            for phase_cfg in self.orchestrator.PHASE_FLOW:
                phase_id = phase_cfg["id"]
                stats = PhaseStats()

                # A. Accepted/Rejected: Scan entire tree for notes of this phase
                for paper_key, notes in item_notes.items():
                    phase_decision = self._get_phase_decision_from_parsed(notes, phase_id)
                    if phase_decision in ["accepted", "included", "approved"]:
                        stats.accepted += 1
                    elif phase_decision in ["rejected", "excluded"]:
                        stats.rejected += 1

                # B. Pending: Items physically in the QUEUE folder WITHOUT a note for THIS phase
                queue_items = list(self.gateway.get_items_in_collection(current_queue_key, top_only=True))
                for q_item in queue_items:
                    if q_item.item_type in ["attachment", "note"]:
                        continue

                    notes = item_notes.get(q_item.key, [])
                    if self._get_phase_decision_from_parsed(notes, phase_id) is None:
                        stats.pending += 1

                status.phases[phase_id] = stats

                # Advance queue folder: current phase's 'folder' is the queue for the NEXT phase
                current_queue_key = phase_map.get(phase_cfg["folder"])
                if not current_queue_key:
                    break

            results.append(status)

        return results

    def get_pending_items(self, root_key: Optional[str] = None) -> List[PendingItem]:
        all_collections = self.gateway.get_all_collections()

        if root_key:
            actual_root = self.gateway.get_collection_id_by_name(root_key) or root_key
            raw_collections = [c for c in all_collections if c["key"] == actual_root]
            if not raw_collections:
                return []
        else:
            raw_collections = [
                c for c in all_collections
                if c["data"]["name"].startswith("raw_") and not c["data"].get("parentCollection")
            ]

        pending_items = []
        for raw_col in raw_collections:
            source_key = raw_col["key"]
            source_name = raw_col["data"]["name"]

            phase_map = self.orchestrator.ensure_slr_hierarchy(source_key, all_collections)

            current_queue_key = source_key

            for phase_cfg in self.orchestrator.PHASE_FLOW:
                phase_id = phase_id = phase_cfg["id"]
                queue_items = list(self.gateway.get_items_in_collection(current_queue_key, top_only=True))

                for paper in queue_items:
                    if paper.item_type in ["attachment", "note"]:
                        continue

                    children = self.gateway.get_item_children(paper.key)
                    decision = self._get_phase_decision(children, phase_id)

                    if decision is None:
                        reason = f"Missing audit note for {phase_id}."
                        pending_items.append(PendingItem(
                            item_key=paper.key,
                            title=paper.title or "Untitled",
                            source_collection=source_name,
                            phase=phase_id,
                            reason=reason
                        ))

                current_queue_key = phase_map.get(phase_cfg["folder"])
                if not current_queue_key:
                    break

        return pending_items

    def _get_phase_decision_from_parsed(self, parsed_notes: List[dict], phase_id: str) -> Optional[str]:
        """Specialized check for QA scores or simple decisions."""
        for note in parsed_notes:
            if note.get("phase") == phase_id:
                # Handle Quality Assessment victory condition logic
                if phase_id == "quality_assessment":
                    # Re-use orchestrator logic if possible, but keep it self-contained for now
                    qa_block = note.get("quality_assessment", {})
                    if not isinstance(qa_block, dict):
                        qa_block = note.get("data", {}).get("quality_assessment", {})

                    raw_total = qa_block.get("total") if isinstance(qa_block, dict) else None
                    if raw_total is not None:
                        try:
                            # If it has a total score, we consider it 'decided'.
                            # 'Accepted' vs 'Rejected' depends on the score, but here
                            # we just return the 'decision' field if present or infer from score.
                            decision = note.get("decision")
                            if not decision:
                                limit = qa_block.get("limit") or qa_block.get("threshold") or 2.0
                                decision = "accepted" if float(raw_total) >= float(limit) else "rejected"
                            return decision.lower()
                        except (ValueError, TypeError):
                            pass

                return str(note.get("decision", "")).lower()
        return None

    def _get_phase_decision(self, children: List[dict], phase_id: str) -> Optional[str]:
        parsed_notes = []
        for child in children:
            if child.get("data", {}).get("itemType") == "note":
                parsed = parse_sdb_note(child.get("data", {}).get("note", ""))
                if parsed:
                    parsed_notes.append(parsed)
        return self._get_phase_decision_from_parsed(parsed_notes, phase_id)
