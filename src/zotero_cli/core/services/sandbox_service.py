import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from zotero_cli.core.interfaces import CollectionRepository, ItemRepository, NoteRepository

DEFAULT_SANDBOX_NAME = "Zotero-CLI Sandbox"


class SandboxService:
    """
    Provisions (or tears down) a temporary Zotero collection populated with
    mock papers, so a new user can try screening/reporting/RAG commands
    without touching their real library. See `system demo-sandbox`.
    """

    def __init__(
        self,
        collection_repo: CollectionRepository,
        item_repo: ItemRepository,
        note_repo: NoteRepository,
    ):
        self.collection_repo = collection_repo
        self.item_repo = item_repo
        self.note_repo = note_repo

    def create_sandbox(self, name: str = DEFAULT_SANDBOX_NAME) -> Tuple[str, int]:
        """
        Creates a collection named `name` populated with the bundled mock
        dataset. Returns (collection_name, items_created).
        """
        dataset = self._load_dataset()

        collection_id = self.collection_repo.create_collection(name)
        if not collection_id:
            raise RuntimeError(f"Failed to create sandbox collection '{name}'.")

        created = 0
        for paper in dataset:
            item_data = self.item_repo.get_item_template("journalArticle")
            item_data["title"] = paper["title"]
            item_data["abstractNote"] = paper.get("abstract", "")
            item_data["date"] = paper.get("date", "")
            item_data["creators"] = [
                self._split_creator(full_name) for full_name in paper.get("creators", [])
            ]
            item_data["tags"] = [{"tag": t} for t in paper.get("tags", [])]
            item_data["collections"] = [collection_id]

            item_key = self.item_repo.create_generic_item(item_data)
            if not item_key:
                continue
            created += 1

            if paper.get("seed_sdb"):
                self._seed_mock_sdb_note(item_key)

        return name, created

    def clean_sandbox(self, name: str = DEFAULT_SANDBOX_NAME) -> bool:
        """Deletes the named sandbox collection, if it exists. Returns False if not found."""
        collection_id = self.collection_repo.get_collection_id_by_name(name)
        if not collection_id:
            return False

        collection = self.collection_repo.get_collection(collection_id)
        if not collection:
            return False

        version = int(collection.get("version") or 0)
        return self.collection_repo.delete_collection(collection_id, version)

    def _load_dataset(self) -> List[Dict[str, Any]]:
        template_path = Path(__file__).parent.parent.parent / "templates" / "demo_sandbox.yaml"
        if not template_path.exists():
            raise FileNotFoundError(f"Sandbox dataset not found at {template_path}")
        with open(template_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        papers: List[Dict[str, Any]] = data.get("papers", [])
        return papers

    @staticmethod
    def _split_creator(full_name: str) -> Dict[str, str]:
        parts = full_name.rsplit(" ", 1)
        first_name, last_name = (parts[0], parts[1]) if len(parts) == 2 else ("", full_name)
        return {"creatorType": "author", "firstName": first_name, "lastName": last_name}

    def _seed_mock_sdb_note(self, item_key: str) -> None:
        payload = {
            "audit_version": "1.2",
            "decision": "accepted",
            "reason_code": [],
            "reason_text": "Demonstrates a screened item for onboarding.",
            "evidence": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "zotero-cli-demo-sandbox",
            "persona": "demo",
            "phase": "title_abstract",
            "action": "screening_decision",
        }
        note_content = f"<div>{json.dumps(payload, indent=2)}</div>"
        self.note_repo.create_note(item_key, note_content)
