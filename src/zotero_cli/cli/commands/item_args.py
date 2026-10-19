"""Argument definitions of the `item` verbs (the parser side of item_cmd.py)."""

import argparse

from zotero_cli.cli.commands import item_annotations
from zotero_cli.cli.flags import add_bibliography_flags, add_details_flag
from zotero_cli.cli.safety import add_permanent_flag

ITEM_KEY_HELP = "Item Key"


def add_move_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Move
    move_p = sub.add_parser(
        "move",
        help="Move item between collections",
        description="Moves a research item from one collection to another by updating its collection links in the Zotero library.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Categorizing a paper into a specific folder
Problem: I have a paper in "Incoming Search" (Key: INC_01) and I want to move it to my "Methodology" folder (Key: METH_01).
Action:  zotero-cli item move --key "ABCD1234" --source "INC_01" --target "METH_01"
Result:  The item is now correctly linked to the "Methodology" folder and removed from "Incoming Search."

Notes
-----
• Common Failure Modes: Attempting to move an item using a name for the source or target that corresponds to multiple collections. This will lead to an ambiguity error.
• Safety Tips: Always use item list or collection list to find the exact keys before moving critical items. Moving an item does not affect its metadata or attachments.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_move.md
""",
    )
    move_p.add_argument("--key", required=True, help="Key of the item to move")
    move_p.add_argument("--source", help="Source collection (optional if unambiguous)")
    move_p.add_argument("--target", required=True, help="Destination collection name or key")


def add_list_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # List (Subset of list items)
    list_p = sub.add_parser(
        "list",
        help="List items in a collection",
        description="Displays a table of research items within a collection, the trash, or unfiled at the library root. For filtering by screening decision (included/excluded), phase, or persona, use `slr list` instead.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Browsing everything in a folder
Problem: I want to see all items currently in my "Final Selection" folder (Key: FIN_01).
Action:  zotero-cli item list --collection "FIN_01"
Result:  The table displays every item in that collection, showing their titles and unique keys.

Scenario: Filtering by tag instead
Problem: I want only the items I tagged "accepted", not everything in the folder.
Action:  zotero-cli search --collection "FIN_01" --tag accepted
Result:  Only the items in that collection carrying the tag are shown.

Scenario: Exporting bibliographic metadata for a report
Problem: I need authors, year, venue and DOI for every paper in a collection, in a spreadsheet.
Action:  zotero-cli item list --collection "FIN_01" --fields key,title,creators,year,venue,doi --format csv > fin_01.csv
Result:  A CSV with one row per item and the requested columns. Use --wide for a quick on-screen view.

Notes
-----
• Common Failure Modes: Confusion between the --collection name and key. For deterministic results, always prefer using the unique Key.
• Safety Tips: Use the --top-only flag if you want to exclude child attachments and notes from the list for a cleaner view.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_list.md
""",
    )
    list_p.add_argument("--collection", help="Collection name or key")
    list_p.add_argument("--trash", action="store_true", help="List items in the trash")
    list_p.add_argument(
        "--root", action="store_true", help="List top-level items not in any collection"
    )
    list_p.add_argument("--top-only", action="store_true", help="Only show top-level items")
    fields_group = list_p.add_mutually_exclusive_group()
    fields_group.add_argument(
        "--fields",
        help=(
            "Comma-separated fields to show, e.g. key,title,creators,year,venue,doi. "
            "Also accepts raw Zotero field names such as publicationTitle or volume."
        ),
    )
    fields_group.add_argument(
        "-w",
        "--wide",
        action="store_true",
        help="Preset: key, title, first author, year, venue, DOI",
    )
    list_p.add_argument(
        "-f",
        "--format",
        choices=["table", "json", "csv", "ndjson", "keys", "markdown"],
        default="table",
        help="Output format (Default: table)",
    )


def add_update_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Update
    update_p = sub.add_parser(
        "update",
        help="Update item metadata",
        description="Corrects or enhances the metadata of an individual Zotero item, including fields such as Title, DOI, and Abstract.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Correcting a title with typos
Problem: My paper with key ABCD1234 has a typo in the title: "Attension is all you need."
Action:  zotero-cli item update --key "ABCD1234" --title "Attention is All You Need"
Result:  The title is correctly updated in the Zotero library.

Notes
-----
• Common Failure Modes: Attempting to update an item using a malformed JSON string. Always validate your JSON structure before running the command.
• Safety Tips: Use the targeted flags (--title, --doi) for simple corrections. The --json flag can modify any Zotero field if correctly formatted.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_update.md
""",
    )
    update_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
    update_p.add_argument("--doi", help="Update DOI")
    update_p.add_argument("--title", help="Update Title")
    update_p.add_argument("--abstract", help="Update Abstract")
    update_p.add_argument("--json", help="Update using raw JSON string")
    update_p.add_argument("--version", type=int, help="Current version (auto-resolved if omitted)")


def add_pdf_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # PDF operations
    pdf_p = sub.add_parser(
        "pdf",
        help="PDF attachment operations",
        description="Manages PDF attachments for a single item in your Zotero library, including fetching files from online sources, removing existing ones, or attaching local files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_pdf.md
""",
    )
    pdf_sub = pdf_p.add_subparsers(dest="pdf_verb", required=True)

    fetch_p = pdf_sub.add_parser(
        "fetch",
        help="Fetch missing PDF for a specific item",
        description="Automatically attempts to retrieve a PDF for the item from the internet using its DOI or ArXiv ID metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
$ zotero-cli item pdf fetch --key ABCD1234
$ zotero-cli item pdf fetch --collection "To Read"

Notes
-----
• Common Failure Modes: Attempting to fetch for an item without valid DOI metadata.
• Safety Tips: Use fetch as your first attempt for mass metadata enrichment.
""",
    )
    fetch_p.add_argument("--key", help=ITEM_KEY_HELP)
    fetch_p.add_argument("--collection", help="Fetch PDFs for all items in a collection")
    fetch_p.add_argument("--file", help="Fetch PDFs for all items in a key-list file")
    add_details_flag(fetch_p, "Print each fetch attempt")

    strip_p = pdf_sub.add_parser(
        "strip",
        help="Remove PDF attachments from a specific item",
        description="Permanently deletes all existing PDF attachments linked to the item from the Zotero library.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
$ zotero-cli item pdf strip --key ABCD1234 --execute

Notes
-----
• Common Failure Modes: strip is irreversible and will permanently delete files from your Zotero storage.
""",
    )
    strip_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
    strip_p.add_argument("--execute", action="store_true", help="Actually perform deletions")
    add_details_flag(strip_p, "Print each item stripped")

    attach_p = pdf_sub.add_parser(
        "attach",
        help="Attach a local file to an item",
        description="Manually uploads a local file from your computer and links it as a child attachment to the item in Zotero.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Manually attaching a downloaded paper
Problem: I've manually downloaded a paper ("Manual_Ref.pdf") and want to attach it to its corresponding item (Key: REF_123) in Zotero.
Action:  zotero-cli item pdf attach --key "REF_123" --file "Manual_Ref.pdf"
Result:  The PDF is uploaded and linked to the item in the Zotero cloud storage.

Notes
-----
• Common Failure Modes: Attaching a file that is too large for your Zotero storage quota.
""",
    )
    attach_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
    attach_p.add_argument("--file", required=True, help="Path to local file")


def add_hydrate_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Hydrate
    hydrate_p = sub.add_parser(
        "hydrate",
        help="Fill in missing metadata from external sources (DOI, arXiv, PubMed, ...)",
        description="Fills in missing metadata (abstract, date, venue, URL, creators, DOI) for items that have a DOI, an arXiv ID or a PMID, looking them up across the configured metadata providers (Semantic Scholar, CrossRef, OpenAlex, PubMed, ...). Previews by default; pass --execute to write.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Completing records imported from a BibTeX/CSV export
Problem: A collection imported from a reference export has DOIs but no abstracts or venues.
Action:  zotero-cli item hydrate --collection "Imported" && zotero-cli item hydrate --collection "Imported" --execute
Result:  The first run previews, per item and field, what would be filled in; the second writes it. Fields that already have a value are left alone.

Scenario: Catching up arXiv preprints that have since been published
Problem: Items imported from arXiv have no DOI or journal yet.
Action:  zotero-cli item hydrate --collection "ARXIV_FOLDER" --execute
Result:  Preprints whose published version arXiv knows get its DOI and journal, then any other empty fields from the providers.

Scenario: Letting a script or agent review changes first
Problem: I want machine-readable proposed changes before anything is written.
Action:  zotero-cli item hydrate --all --format json > proposals.json
Result:  One JSON object per item: status, identifier used, and every proposed change with its old and new value.

Notes
-----
• Nothing is written without --execute. Only empty fields are filled unless you pass --overwrite, and the title is never changed unless you name it in --fields.
• Items with no DOI, arXiv ID or PMID are skipped; --by-title tries an exact title match (also checking year and first author) and skips anything less certain.
• --offline is read-only: previews work, --execute doesn't.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_hydrate.md
""",
    )
    hydrate_scope = hydrate_p.add_mutually_exclusive_group()
    hydrate_scope.add_argument("--key", help=ITEM_KEY_HELP)
    hydrate_scope.add_argument("--collection", help="Hydrate all items in a collection")
    hydrate_scope.add_argument("--all", action="store_true", help="Hydrate the whole library")
    hydrate_p.add_argument(
        "--fields",
        help="Comma-separated fields to fill: doi, abstract, date, venue, url, creators, title "
        "(default: all but title)",
    )
    hydrate_p.add_argument(
        "--overwrite",
        action="store_true",
        help="Also replace fields that already have a value (title only if named in --fields)",
    )
    hydrate_p.add_argument(
        "--by-title",
        action="store_true",
        help="For items without an identifier, try an exact title match",
    )
    hydrate_write = hydrate_p.add_mutually_exclusive_group()
    hydrate_write.add_argument(
        "--execute", action="store_true", help="Write the changes (default: preview only)"
    )
    hydrate_write.add_argument(
        "--dry-run", action="store_true", help="Preview only (the default; kept for scripts)"
    )
    hydrate_p.add_argument(
        "-f",
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )


def add_purge_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Purge
    purge_p = sub.add_parser(
        "purge",
        help="Purge assets (files, notes, tags) from an item",
        description="Permanently removes specific types of child assets (PDFs, notes, or tags) from a research item without deleting the main bibliographic record itself.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Cleaning up annotations before a re-read
Problem: I have a paper (Key: READ_456) filled with old notes and tags that are no longer relevant to my current project.
Action:  zotero-cli item purge --key "READ_456" --notes --tags
Result:  All notes and tags are removed from the paper, providing a clean slate for new analysis.

Notes
-----
• Common Failure Modes: Attempting to purge assets without providing at least one asset type flag (--files, --notes, or --tags).
• Safety Tips: ALWAYS verify the item key using item inspect before purging. This command is irreversible.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_purge.md
""",
    )
    purge_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
    purge_p.add_argument("--files", action="store_true", help="Purge attachments/files")
    purge_p.add_argument("--notes", action="store_true", help="Purge notes")
    purge_p.add_argument("--tags", action="store_true", help="Purge tags")
    purge_p.add_argument("--force", action="store_true", help="Skip confirmation")


def add_delete_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Delete
    delete_p = sub.add_parser(
        "delete",
        help="Delete an item (to Zotero's trash; --permanent deletes for good)",
        description="Moves a research item to Zotero's trash, exactly as deleting it in Zotero Desktop would (recoverable with `item restore`), or with --permanent deletes it for good, which cannot be undone. Previews by default; --execute applies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Removing a record I might want back
Problem: I manually added a test item (Key: JUNK_01) by mistake and want it gone from my library view.
Action:  zotero-cli item delete --key "JUNK_01" --execute
Result:  The item is in Zotero's trash (and Desktop's); `item restore --key "JUNK_01" --execute` brings it back.

Scenario: Removing a record for good
Problem: I'm sure I want JUNK_01 gone entirely.
Action:  zotero-cli item delete --key "JUNK_01" --permanent --execute
Result:  The item is permanently removed from the library. This cannot be undone.

Scenario: Checking what a delete would remove before committing to it
Problem: I want to see the item and its attachments/notes before deleting it.
Action:  zotero-cli item delete --key "JUNK_01" --dry-run
Result:  The item and its children are listed; nothing is deleted.

Notes
-----
• Common Failure Modes: Assuming --permanent is recoverable: it is not. Without it the item goes to Zotero's trash and `item restore` brings it back.
• Safety Tips: ALWAYS verify the item key using item inspect before deleting. For consolidating duplicates instead of discarding one outright, use item merge.
• Previews by default: nothing is deleted until you pass --execute. The item goes to Zotero's trash unless you pass --permanent.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_delete.md
""",
    )
    delete_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
    delete_p.add_argument(
        "--version",
        type=int,
        help="Delete only if the item is still at this version (default: its current version)",
    )
    delete_p.add_argument(
        "--trash",
        action="store_true",
        help="Move the item to Zotero's trash (the default; accepted for scripts written for 3.x)",
    )
    add_permanent_flag(delete_p, "the item")
    delete_mode = delete_p.add_mutually_exclusive_group()
    delete_mode.add_argument(
        "--execute",
        action="store_true",
        help="Delete the item (without it, only a preview is shown)",
    )
    delete_mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the item and its children without deleting",
    )


def add_trash_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Trash
    trash_p = sub.add_parser(
        "trash",
        help="Move an item to Zotero's trash (recoverable)",
        description="Moves an item into Zotero's trash, exactly as deleting it in Zotero Desktop would. Online it sets the item's `deleted` flag through the Web API, which Desktop syncs; with --offline it writes the same rows Desktop itself writes to the local zotero.sqlite. Either way the item shows in Desktop's trash and `item restore` brings it back. Previews by default; --execute applies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Getting rid of a duplicate in a way I can undo
Problem: I want to trash item ABCD1234, the same as clicking delete in Zotero Desktop.
Action:  zotero-cli item trash --key "ABCD1234" --execute
Result:  The item is in Zotero's trash, in the library and in Desktop after its next sync.

Scenario: The same, against the local database
Action:  zotero-cli --offline item trash --key "ABCD1234" --execute
Result:  The row is written to zotero.sqlite; Desktop pushes it to the server on its next sync.

Notes
-----
• Common Failure Modes: the item changed on the server since it was read (the command fails and trashes nothing - run it again); with --offline, running while Zotero Desktop is actively writing to the same file - fails cleanly with a lock error, just retry or close Desktop first.
• Safety Tips: Recoverable via `item restore`, unless you also run Desktop's "Empty Trash". With --offline, close Desktop first to avoid a database lock; a backup of zotero.sqlite is made before the first write.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_trash.md
""",
    )
    trash_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
    trash_p.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the write (default: preview only)",
    )
    trash_p.add_argument(
        "--force", action="store_true", help="Skip the interactive confirmation prompt"
    )


def add_annotations_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Annotations
    annotations_p = sub.add_parser(
        "annotations",
        help="Show the PDF highlights and notes of an item",
        description="Lists the annotations (highlights, notes, underlines, images, ink, text) you made in an item's PDF attachments, in reading order, with the highlighted text, your comment, colour, page and tags. Read-only; works with the Web API and with --offline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=item_annotations.EPILOG,
    )
    item_annotations.register_args(annotations_p)


def add_restore_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Restore
    restore_p = sub.add_parser(
        "restore",
        help="Restore an item from Zotero's trash",
        description="Takes a trashed item out of the trash, as restoring it in Zotero Desktop would. Online it clears the item's `deleted` flag through the Web API; with --offline it writes the same rows Desktop itself writes to the local zotero.sqlite. Previews by default; --execute applies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Undoing an accidental trash
Problem: I ran `item trash --key ABCD1234 --execute` by mistake and want it back.
Action:  zotero-cli item restore --key "ABCD1234" --execute
Result:  The item leaves the trash and appears normally again, in its old collections.

Scenario: The same, against the local database
Action:  zotero-cli --offline item restore --key "ABCD1234" --execute

Notes
-----
• Common Failure Modes: trying to restore an item that was permanently deleted (`item delete --permanent`, or Desktop's "Empty Trash") - restore only works before that point; the item changed on the server since it was read (the command fails and restores nothing - run it again).
• Safety Tips: With --offline, close Desktop first to avoid a database lock.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_restore.md
""",
    )
    restore_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
    restore_p.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the write (default: preview only)",
    )
    restore_p.add_argument(
        "--force", action="store_true", help="Skip the interactive confirmation prompt"
    )


def add_transfer_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Transfer
    transfer_p = sub.add_parser(
        "transfer",
        help="Transfer item between different libraries",
        description="Copies or moves a research item (including its metadata and PDF attachments) from your personal library to a Zotero group library, or between different groups.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Moving a paper to a shared project group
Problem: I've found a perfect paper in my personal library and I want to share it with my lab's Zotero group (ID: 987654).
Action:  zotero-cli item transfer --key "ABCD1234" --target-group "987654"
Result:  A duplicate of the paper and its PDF is created in the lab's group library.

Scenario: Moving it, but keeping the original recoverable
Problem: I want the paper out of my personal library once it's safely in the group, without losing it for good.
Action:  zotero-cli item transfer --key "ABCD1234" --target-group "987654" --delete-source --trash
Result:  After every note and file has been copied, the original goes to Zotero's trash (`item restore` brings it back).

Notes
-----
• Common Failure Modes: Attempting to transfer to a group for which you do not have "Write" permissions.
• Safety Tips: Always verify target group ID via system groups. Cross-library transfers can take time.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_transfer.md
""",
    )
    transfer_p.add_argument("--key", required=True, help="Zotero Item Key")
    transfer_p.add_argument("--target-group", required=True, help="Target Group ID")
    transfer_p.add_argument(
        "--delete-source",
        action="store_true",
        help="Delete item from source library after transfer",
    )
    transfer_p.add_argument(
        "--trash",
        action="store_true",
        help="With --delete-source: move the source item to Zotero's trash (the default; accepted for scripts written for 3.x)",
    )
    add_permanent_flag(transfer_p, "the source item (with --delete-source)")


def add_export_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Export
    export_p = sub.add_parser(
        "export",
        help="Export item metadata or content",
        description="Exports a single Zotero item: its metadata as BibTeX or RIS to a file (--output is required), or the text of its PDF as a .md file (md). To print BibTeX/RIS to the terminal instead, use `item inspect --key KEY --format bibtex`.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Getting a BibTeX entry for a specific citation
Problem: I'm writing a paper and I just need the BibTeX code for the item with key VA12345.
Action:  zotero-cli item export --key "VA12345" --as bibtex --output va12345.bib
Result:  The BibTeX entry is written to va12345.bib. (`zotero-cli item inspect --key "VA12345" --as bibtex`
         prints it to the terminal instead.)

Notes
-----
• Common Failure Modes: Attempting to export an item key that doesn't exist or for which metadata is incomplete.
• Safety Tips: Use the md format to generate a local Markdown "Digital Twin" of your Zotero item.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_export.md
""",
    )
    export_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
    export_p.add_argument(
        "--as",
        dest="export_format",
        choices=["bibtex", "ris", "md", "bibliography"],
        default="bibtex",
        help="Export type",
    )
    add_bibliography_flags(export_p)
    export_p.add_argument("--output", help="Output file path or directory (for md)")
    export_p.add_argument(
        "--annotations",
        action="store_true",
        help="With --as md: end the file with the item's PDF annotations (highlights, notes)",
    )


def add_add_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Add
    add_p = sub.add_parser(
        "add",
        help="Manually add a new item to a collection",
        description="Manually creates a new research item in a specific Zotero collection by providing core bibliographic fields directly from the terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Manually adding an internal technical report
Problem: I have a PDF of an internal company report that isn't online and I want to add it to my "References" folder (Key: REF_01).
Action:  zotero-cli item add --title "Advanced RAG Pipelines V2" --authors "Engineering Team" --collection "REF_01" --type report
Result:  A new item of type "report" is created in Zotero, ready for PDF attachment.

Notes
-----
• Common Failure Modes: Attempting to run without providing the mandatory --title or --collection flags.
• Safety Tips: Use item pdf attach immediately after creation if you have a local file for the item.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_add.md
""",
    )
    add_p.add_argument("--collection", required=True, help="Collection name or key")
    add_p.add_argument("--title", required=True, help="Item Title")
    add_p.add_argument(
        "--type", default="journalArticle", help="Item Type (Default: journalArticle)"
    )
    add_p.add_argument("--authors", help="Comma-separated authors (e.g. 'John Doe, Jane Smith')")
    add_p.add_argument("--date", help="Publication Date")
    add_p.add_argument("--abstract", help="Abstract/Note")


def add_merge_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Merge
    merge_p = sub.add_parser(
        "merge",
        help="Merge duplicate items into one survivor",
        description="Merges one or more duplicate items into a chosen master: unions tags and collection membership, moves notes/attachments onto the master, then moves the (now emptied) duplicates to Zotero's trash so the merge can be undone - or, with --permanent, deletes them for good. Use `report duplicates` first to find candidate keys, or `report duplicates --export-plan` for a bulk-editable plan file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
Scenario: Consolidating a paper imported twice from different search databases
Problem: report duplicates found the same paper as items IEEE_KEY1 (master, more complete) and SPR_KEY2 (duplicate).
Action:  zotero-cli item merge --master "IEEE_KEY1" --duplicates "SPR_KEY2" --execute
Result:  SPR_KEY2's tags, collections, notes, and attachments move onto IEEE_KEY1; SPR_KEY2 goes to Zotero's trash and `item restore --key "SPR_KEY2" --execute` brings it back (its notes and attachments stay on the master).

Scenario: Consolidating for good
Problem: I'm sure the two records are the same paper and want no leftovers.
Action:  zotero-cli item merge --master "IEEE_KEY1" --duplicates "SPR_KEY2" --permanent --execute
Result:  The same merge, but SPR_KEY2 is deleted for good; there is no undo.

Scenario: Previewing a merge before committing
Problem: I want to see what a merge would do without touching my library yet.
Action:  zotero-cli item merge --master "IEEE_KEY1" --duplicates "SPR_KEY2"
Result:  A preview table is shown (tags/collections to add, notes/attachments to move); nothing is written since --execute was omitted.

Scenario: Bulk-resolving a batch of duplicate groups from a plan file
Problem: I exported duplicates.csv via `report duplicates --export-plan`, filled in the role/reason columns for every group, and want to commit them all at once.
Action:  zotero-cli item merge --from-plan duplicates.csv --execute
Result:  Every fully-resolved group is merged in one pass; if any group is still missing a decision, nothing is written and the incomplete groups are listed.

Notes
-----
• Common Failure Modes: Master and duplicates must share the same item type - Zotero Desktop enforces the same rule. Conflicting scalar fields (title, date, DOI, ISBN, URL, abstract) must be resolved interactively (single-group form) before --execute can proceed; there is no silent "first wins" default. With --from-plan, an incomplete plan (any group missing a decision) blocks the entire batch, not just that group.
• Safety Tips: The duplicates go to Zotero's trash and can be restored (their notes and attachments stay on the master). With --permanent they are deleted for good and there is no undo. Run without --execute first to preview. Any citation-management document referencing a duplicate's key by that key will break.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_merge.md
""",
    )
    merge_p.add_argument("--master", help="Zotero Key of the item to keep")
    merge_p.add_argument(
        "--duplicates",
        help="Comma-separated Zotero Keys of the duplicate items to merge into --master",
    )
    merge_p.add_argument(
        "--from-plan",
        help="Path to a merge plan file (.csv or .json, from `report duplicates --export-plan`) "
        "for bulk execution instead of a single --master/--duplicates group",
    )
    merge_p.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the merge (default: preview only)",
    )
    merge_p.add_argument("--force", action="store_true", help="Skip the confirmation prompt")
    merge_p.add_argument(
        "--trash",
        action="store_true",
        help="Move the emptied duplicates to Zotero's trash (the default; accepted for scripts written for 3.x)",
    )
    add_permanent_flag(merge_p, "the emptied duplicates")
