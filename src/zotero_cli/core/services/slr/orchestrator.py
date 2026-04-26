import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.utils.sdb_parser import parse_sdb_note
from zotero_cli.core.zotero_item import ZoteroItem


class SLROrchestrator:
    """
    Central service for SLR protocol enforcement, hierarchy management,
    and state-to-folder mapping.
    """

    # The canonical definition of our SLR 4-Step Process
    PHASE_FLOW = [
        {"id": "title_abstract", "folder": "1-title_abstract", "label": "1-T&A"},
        {"id": "full_text", "folder": "2-fulltext", "label": "2-FT"},
        {"id": "quality_assessment", "folder": "3-quality_assessment", "label": "3-QA"},
        {"id": "data_extraction", "folder": "4-data_extraction", "label": "4-DE"},
    ]

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def ensure_slr_hierarchy(
        self, parent_key: str, all_cols: Optional[List[dict]] = None
    ) -> Dict[str, str]:
        """
        Verifies and silently creates the 4-phase subfolders under a source collection.
        Returns a mapping of folder_name -> folder_key.
        """
        if all_cols is None:
            all_cols = self.gateway.get_all_collections()

        existing_subfolders = {
            c["data"]["name"]: c["key"]
            for c in all_cols
            if c["data"].get("parentCollection") == parent_key
        }

        phase_map = {}
        for phase_cfg in self.PHASE_FLOW:
            name = phase_cfg["folder"]
            if name in existing_subfolders:
                phase_map[name] = existing_subfolders[name]
            else:
                # Create missing folder
                new_key = self.gateway.create_collection(name, parent_key=parent_key)
                if new_key:
                    phase_map[name] = new_key
        return phase_map

    def get_tree_keys(self, root_key: str, all_cols: Optional[List[dict]] = None) -> List[str]:
        """
        Returns a list of all keys belonging to a specific SLR tree (root + phase folders).
        Used for exclusive membership enforcement.
        """
        phase_map = self.ensure_slr_hierarchy(root_key, all_cols)
        keys = [root_key]
        keys.extend(phase_map.values())
        return keys

    def get_all_papers_in_tree(self, root_key: str) -> List[ZoteroItem]:
        """
        Collects every unique top-level paper existing in the root or phase folders.
        """
        tree_keys = self.get_tree_keys(root_key)
        unique_papers = {}

        for key in tree_keys:
            items = self.gateway.get_items_in_collection(key, top_only=True)
            for item in items:
                if item.item_type not in ["attachment", "note"]:
                    unique_papers[item.key] = item

        return list(unique_papers.values())

    def resolve_target_phase(
        self, item_key: str, default_qa_threshold: Optional[float] = None
    ) -> Optional[str]:
        """
        Determines the highest phase an item reached by validating the SLR pipeline
        sequentially. A paper stops advancing at the FIRST phase it fails to win.
        """
        # Use system default if not provided
        threshold = default_qa_threshold if default_qa_threshold is not None else 2.0

        children = self.gateway.get_item_children(item_key)

        # Parse all notes once to avoid repeated parsing in the loop
        parsed_notes = []
        for child in children:
            if child.get("data", {}).get("itemType") == "note":
                parsed = parse_sdb_note(child.get("data", {}).get("note", ""))
                if parsed:
                    parsed_notes.append(parsed)

        highest_won_phase_id = None

        # Iterate through the pipeline in strict order
        for phase_cfg in self.PHASE_FLOW:
            phase_id = phase_cfg["id"]

            # Check if any note for THIS phase satisfies the victory condition
            phase_notes = [n for n in parsed_notes if n.get("phase") == phase_id]

            won_this_phase = False
            for note in phase_notes:
                if self._evaluate_phase_success(phase_id, note, threshold):
                    won_this_phase = True
                    break
            if won_this_phase:
                highest_won_phase_id = phase_id
            else:
                # PIPELINE BREAK: Paper failed this gate. It cannot advance further.
                break

        return highest_won_phase_id

    def _evaluate_phase_success(
        self, phase_id: str, note_data: dict, default_threshold: float
    ) -> bool:
        """
        Victory Condition Strategy.
        - quality_assessment: total >= threshold
        - others: decision == accepted/approved/included
        """
        if phase_id == "quality_assessment":
            # Extract total score
            qa_block = note_data.get("quality_assessment", {})
            if not isinstance(qa_block, dict):
                # Handle legacy/flat structure if present
                qa_block = note_data.get("data", {}).get("quality_assessment", {})

            raw_total = qa_block.get("total") if isinstance(qa_block, dict) else None

            if raw_total is None:
                return False

            try:
                total = float(raw_total)
                # Look for 'limit' or 'threshold' in the note, fall back to system default
                limit = qa_block.get("limit") or qa_block.get("threshold") or default_threshold
                return total >= float(limit)
            except (ValueError, TypeError):
                return False

        # Default string-based decision gate
        decision = str(note_data.get("decision", "")).lower()
        return decision in ["accepted", "approved", "included"]

    def get_folder_key_for_phase(self, root_key: str, phase_id: Optional[str]) -> str:
        """
        Maps a phase_id to its actual Zotero folder key within the tree.
        If phase_id is None, returns the root_key.
        """
        if not phase_id:
            return root_key

        phase_map = self.ensure_slr_hierarchy(root_key)

        # Find folder name for the ID
        target_folder_name = next(
            (p["folder"] for p in self.PHASE_FLOW if p["id"] == phase_id), None
        )

        if target_folder_name and target_folder_name in phase_map:
            return phase_map[target_folder_name]

        return root_key

    def get_promotion_path(self, root_key: str, phase_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Returns (source_folder_key, target_folder_key) for a given phase promotion.
        """
        phase_map = self.ensure_slr_hierarchy(root_key)
        phase_ids = [p["id"] for p in self.PHASE_FLOW]

        if phase_id not in phase_ids:
            return None, None

        idx = phase_ids.index(phase_id)
        target_folder_name = self.PHASE_FLOW[idx]["folder"]
        target_key = phase_map.get(target_folder_name)

        source_key: Optional[str] = None
        if idx == 0:
            source_key = root_key
        else:
            prev_folder_name = self.PHASE_FLOW[idx - 1]["folder"]
            source_key = phase_map.get(prev_folder_name)

        return source_key, target_key

    def record_duplicate_resolution(self, item_key: str, duplicate_key: str, reason: str):
        """
        Records a permanent audit trail in SDB for duplicate resolution.
        """
        audit_note = {
            "audit_version": "1.2",
            "phase": "system",
            "action": "duplicate_detected",
            "decision": "merged",
            "reason_text": f"{reason}. Removed Duplicate Key: {duplicate_key}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "persona": "orchestrator",
            "agent": "zotero-cli",
        }

        self.gateway.create_note(item_key, json.dumps(audit_note))
