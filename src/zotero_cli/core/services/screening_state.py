import csv
import os
from datetime import datetime
from typing import Any, List, Set


class ScreeningStateService:
    """
    Manages local persistent state for screening sessions.
    Prevents re-screening items and allows resuming interrupted sessions.
    """

    def __init__(self, state_file: str):
        self.state_file = state_file
        self.screened_keys: Set[str] = set()
        self._load_state()

    def _load_state(self):
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

    def is_screened(self, item_key: str) -> bool:
        return item_key in self.screened_keys

    def record_decision(self, item_key: str, decision: str, code: str, persona: str, phase: str):
        """Appends a decision to the state file."""
        file_exists = os.path.exists(self.state_file)

        try:
            with open(self.state_file, "a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["Timestamp", "Key", "Decision", "Code", "Persona", "Phase"]
                )
                if not file_exists:
                    writer.writeheader()

                writer.writerow(
                    {
                        "Timestamp": datetime.now().isoformat(),
                        "Key": item_key,
                        "Decision": decision,
                        "Code": code,
                        "Persona": persona,
                        "Phase": phase,
                    }
                )
            self.screened_keys.add(item_key)
        except Exception as e:
            print(f"Error writing to state file: {e}")

    def filter_pending(self, items: List[Any]) -> List[Any]:
        """Filters out items that have already been screened."""
        return [item for item in items if item.key not in self.screened_keys]
