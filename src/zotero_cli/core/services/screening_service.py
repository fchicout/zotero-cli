import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from zotero_cli.core.interfaces import (
    CollectionRepository,
    ItemRepository,
    NoteRepository,
    TagRepository,
)
from zotero_cli.core.interfaces import (
    ScreeningService as IScreeningService,
)
from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.utils.sdb_parser import parse_sdb_note
from zotero_cli.core.zotero_item import ZoteroItem


class ScreeningService(IScreeningService):
    """
    Service responsible for recording screening decisions and managing item movement.
    Provides the core logic for both CLI 'decision' command and TUI 'screen' mode.
    """

    def __init__(
        self,
        item_repo: ItemRepository,
        collection_repo: CollectionRepository,
        note_repo: NoteRepository,
        tag_repo: TagRepository,
        collection_service: CollectionService,
    ):
        self.item_repo = item_repo
        self.collection_repo = collection_repo
        self.note_repo = note_repo
        self.tag_repo = tag_repo
        self.collection_service = collection_service

    def record_decision(
        self,
        item_key: str,
        decision: str,  # 'INCLUDE' or 'EXCLUDE'
        code: str,
        reason: Optional[str] = None,
        source_collection: Optional[str] = None,
        target_collection: Optional[str] = None,
        agent: str = "zotero-cli",
        persona: str = "unknown",
        phase: str = "title_abstract",
        evidence: Optional[str] = None,
    ) -> bool:
        """
        Records a screening decision for a Zotero item.
        1. Finds or creates a child note with the decision metadata (JSON).
        2. Applies semantic tags (e.g., rsl:exclude:EC1).
        3. Optionally moves the item from source to target collection.

        A thin convenience wrapper over record_decision_note +
        apply_decision_outcome (Issue #201), kept so today's solo-screening
        callers are unaffected. A double-blind/multi-persona consumer
        should call the two primitives directly instead: record each
        rater's decision independently via record_decision_note, then call
        apply_decision_outcome exactly once - after reconciliation - so the
        shared tags/collection-move represent the final outcome rather than
        firing on every persona's call.
        """
        if not self.record_decision_note(
            item_key,
            decision,
            code,
            reason=reason,
            agent=agent,
            persona=persona,
            phase=phase,
            evidence=evidence,
        ):
            return False

        return self.apply_decision_outcome(
            item_key,
            decision,
            code,
            source_collection=source_collection,
            target_collection=target_collection,
            phase=phase,
        )

    def record_decision_note(
        self,
        item_key: str,
        decision: str,
        code: str,
        reason: Optional[str] = None,
        agent: str = "zotero-cli",
        persona: str = "unknown",
        phase: str = "title_abstract",
        evidence: Optional[str] = None,
    ) -> bool:
        """
        Records (writes or upserts) a single persona's screening-decision
        audit note only - no shared tags, no collection movement (Issue
        #201's step 1, split out of record_decision). Upserts by
        (persona, phase): a second call for the same persona/phase updates
        the existing note in place rather than creating a duplicate, so two
        different personas screening the same item each get their own
        independent, upsert-safe note.
        """
        decision_upper = decision.upper()
        if decision_upper not in ["INCLUDE", "EXCLUDE"]:
            print(
                f"Error: Invalid decision '{decision_upper}'. Must be INCLUDE or EXCLUDE.",
                file=sys.stderr,
            )
            return False

        # Map internal decision to SDB decision
        sdb_decision = "accepted" if decision_upper == "INCLUDE" else "rejected"

        # Check for existing note by persona AND phase using robust parsing
        children = self.note_repo.get_item_children(item_key)
        existing_note_key: Optional[str] = None
        existing_version: int = 0

        for child in children:
            data = child.get("data", child)
            if data.get("itemType") == "note":
                content = data.get("note", "")
                parsed_data = parse_sdb_note(content)

                if parsed_data:
                    # Robust check: does this note belong to the same persona/phase?
                    if parsed_data.get("persona") == persona and parsed_data.get("phase") == phase:
                        existing_note_key = child.get("key") or data.get("key")
                        existing_version = int(child.get("version") or data.get("version") or 0)
                        break

        if sdb_decision == "accepted":
            reason_codes = []
        else:
            reason_codes = [c.strip() for c in code.split(",")] if code else []

        # Create the Audit Note using SDB v1.2
        decision_data = {
            "audit_version": "1.2",
            "decision": sdb_decision,
            "reason_code": reason_codes,
            "reason_text": reason if reason else "",
            "evidence": evidence if evidence else "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "persona": persona,
            "phase": phase,
            "action": "screening_decision",
        }

        note_content = f"<div>{json.dumps(decision_data, indent=2)}</div>"

        if existing_note_key:
            success = self.note_repo.update_note(existing_note_key, existing_version, note_content)
        else:
            success = self.note_repo.create_note(item_key, note_content)

        if not success:
            print(f"Error: Failed to record audit note for item {item_key}.", file=sys.stderr)
            return False

        return True

    def apply_decision_outcome(
        self,
        item_key: str,
        decision: str,
        code: str,
        source_collection: Optional[str] = None,
        target_collection: Optional[str] = None,
        phase: str = "title_abstract",
    ) -> bool:
        """
        Applies the shared, item-level side effects of a *final* screening
        outcome - tags and optional collection movement (Issue #201's steps
        2-3, split out of record_decision). Call this exactly once a
        decision is final: immediately after a solo decision, or after a
        double-blind pair has been reconciled - not once per rater.
        """
        decision_upper = decision.upper()
        if decision_upper not in ["INCLUDE", "EXCLUDE"]:
            print(
                f"Error: Invalid decision '{decision_upper}'. Must be INCLUDE or EXCLUDE.",
                file=sys.stderr,
            )
            return False

        sdb_decision = "accepted" if decision_upper == "INCLUDE" else "rejected"

        # Apply Tags
        tags_to_add = [f"rsl:phase:{phase}"]
        if sdb_decision == "rejected":
            codes = [c.strip() for c in code.split(",")] if code else []
            for c in codes:
                tags_to_add.append(f"rsl:exclude:{c}")
        elif sdb_decision == "accepted":
            tags_to_add.append("rsl:include")

        tag_success = self.tag_repo.add_tags(item_key, tags_to_add)
        if not tag_success:
            print(
                f"Warning: Failed to apply tags {tags_to_add} to item {item_key}.",
                file=sys.stderr,
            )

        # Collection Movement (Optional)
        if source_collection and target_collection:
            move_success = self.collection_service.move_item(
                source_collection, target_collection, item_key
            )
            if not move_success:
                print(
                    f"Warning: Decision recorded but failed to move item {item_key}.",
                    file=sys.stderr,
                )

        return True

    def get_decisions_for_item(self, item_key: str) -> List[Dict[str, Any]]:
        """
        Returns every persona's parsed screening-decision note on an item
        (Issue #201), reusing parse_sdb_note, so a caller can check how many
        independent decisions exist and what each persona decided without
        hand-rolling note scanning (get_pending_items's own tag/note check
        below only answers "has *any* decision been recorded", not "what
        did each persona decide").
        """
        children = self.note_repo.get_item_children(item_key)
        decisions: List[Dict[str, Any]] = []
        for child in children:
            data = child.get("data", child)
            if data.get("itemType") == "note":
                parsed = parse_sdb_note(data.get("note", ""))
                if parsed and parsed.get("action") == "screening_decision":
                    decisions.append(parsed)
        return decisions

    def get_pending_items(self, collection_name: str) -> List[ZoteroItem]:
        """
        Fetches items from a collection that do NOT yet have a screening decision note.
        """
        col_id = self.collection_repo.get_collection_id_by_name(collection_name)
        if not col_id:
            return []

        all_items = self.collection_repo.get_items_in_collection(col_id)
        pending = []

        for item in all_items:
            # FAST PATH: Check tags first
            has_tag_decision = False
            for tag in item.tags:
                if (
                    tag.startswith("rsl:phase:")
                    or tag.startswith("rsl:exclude:")
                    or tag == "rsl:include"
                ):
                    has_tag_decision = True
                    break

            if has_tag_decision:
                continue

            # SLOW PATH: Check note content (Fallback)
            children = self.note_repo.get_item_children(item.key)
            has_decision = False
            for child in children:
                # Handle both direct and nested data structures
                data = child.get("data", child)
                if data.get("itemType") == "note":
                    content = data.get("note", "")
                    if "screening_decision" in content or '"decision"' in content:
                        has_decision = True
                        break

            if not has_decision:
                pending.append(item)

        return pending
