"""Issue #378: every code path that permanently deletes must be reviewed for
a preview/confirmation gate. This fails when a new file starts calling a
delete method, so the new path gets that review before it ships.

Keyed on the delete calls themselves, not command names: a name-based check
("delete", "purge", "clean", ...) would have missed `slr prune` and
`item transfer --delete-source`, which both deleted items.
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "zotero_cli"

DELETE_CALL = re.compile(r"\.(delete_item|delete_collection|delete_tags|trash_item|purge)\(")

# file -> the gate that makes its deletes deliberate
REVIEWED = {
    "cli/commands/collection_cmd.py": "collection delete: --recursive previews, needs --execute and --yes/confirmation",
    "cli/commands/item_cmd.py": "item delete: one named key, version-checked (#384)",
    "cli/commands/rag_cmd.py": "rag purge: local vector store only, explicit --all/--key/--collection",
    "core/services/collection_service.py": "plan_recursive_delete/execute_recursive_delete (#378)",
    "core/services/merge_service.py": "item merge / slr dedupe: preview until --execute",
    "core/services/purge_service.py": "item/collection purge, slr sdb reset: dry_run flag + confirmation",
    "core/services/sandbox_service.py": "system demo-sandbox --clean: only the named sandbox collection",
    "core/services/transfer_service.py": "item transfer --delete-source: only after every child copied (#396)",
    "infra/repositories.py": "repository pass-through",
    "infra/zotero_api.py": "the API client itself",
}


def _files_calling_deletes() -> set:
    return {
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if DELETE_CALL.search(path.read_text(encoding="utf-8"))
    }


def test_every_delete_path_has_been_reviewed():
    unreviewed = _files_calling_deletes() - set(REVIEWED)
    assert not unreviewed, (
        f"New code calls a delete method: {sorted(unreviewed)}. Give it a preview "
        "(--dry-run or preview-until---execute) and, for bulk deletes, a confirmation "
        "(see docs/PROCESS.md, destructive commands), then add it to REVIEWED."
    )


def test_reviewed_list_has_no_stale_entries():
    assert set(REVIEWED) <= _files_calling_deletes()
