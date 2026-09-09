import csv
import logging
import os
from datetime import datetime
from typing import Any, List, Set

from zotero_cli.core.utils.csv_safety import sanitize_csv_row

logger = logging.getLogger(__name__)


class ScreeningStateService:
    """
    Manages local persistent state for screening sessions.
    Prevents re-screening items and allows resuming interrupted sessions.
    """

    def __init__(self, state_file: str):
        self.state_file = state_file
        self.screened_keys: Set[str] = set()
        self._load_state()

    def _load_state(self) -> None:
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = row.get("Key")
                    if key:
                        self.screened_keys.add(key)
        except Exception as e:
            print(f"Warning: Failed to load state file: {e}")
            logger.warning("Failed to load screening state file %s: %s", self.state_file, e)

    def is_screened(self, item_key: str) -> bool:
        return item_key in self.screened_keys

    def record_decision(
        self, item_key: str, decision: str, code: str, persona: str, phase: str
    ) -> None:
        """Appends a decision to the state file."""
        file_exists = os.path.exists(self.state_file)

        try:
            with open(self.state_file, "a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["Timestamp", "Key", "Decision", "Code", "Persona", "Phase"]
                )
                if not file_exists:
                    writer.writeheader()

                # Issue #237: these fields are normally system-generated,
                # but sanitize consistently with every other CSV writer in
                # the project so a later change (e.g. a free-text reason
                # field) can't silently reintroduce formula injection here.
                writer.writerow(
                    sanitize_csv_row(
                        {
                            "Timestamp": datetime.now().isoformat(),
                            "Key": item_key,
                            "Decision": decision,
                            "Code": code,
                            "Persona": persona,
                            "Phase": phase,
                        }
                    )
                )
            self.screened_keys.add(item_key)
        except Exception as e:
            print(f"Error writing to state file: {e}")
            logger.exception("Error writing to screening state file %s", self.state_file)

    def filter_pending(self, items: List[Any]) -> List[Any]:
        """Filters out items that have already been screened."""
        return [item for item in items if item.key not in self.screened_keys]
