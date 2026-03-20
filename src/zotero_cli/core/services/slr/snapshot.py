from typing import List


class SnapshotService:
    """
    Analyzes shifts and changes between collection snapshots.
    """
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
