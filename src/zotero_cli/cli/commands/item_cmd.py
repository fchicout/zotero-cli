import argparse
import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.infra.factory import GatewayFactory

console = Console()

ITEM_KEY_HELP = "Item Key"
ABORTED_NO_WRITES_MSG = "[yellow]Aborted - no writes were made.[/yellow]"


class InspectCommand(BaseCommand):
    name = "inspect"
    help = "Inspect item details"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.description = "Provides a comprehensive view of all metadata, attachments, and child notes associated with a specific Zotero item."
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Verifying metadata after an import
Problem: I've imported a paper and want to ensure the DOI was correctly captured and check for any existing notes.
Action:  zotero-cli item inspect --key "ABCD1234"
Result:  The CLI displays a detailed view of the item, including its DOI, abstract, and list of child PDF attachments.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to inspect an item key that does not exist or for which you lack read permissions.
• Safety Tips: Use item list or search to find the correct key if you are unsure. For very large notes, the --full-notes flag may result in a lot of terminal scroll.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_inspect.md
"""
        parser.add_argument("--key", help="Zotero Item Key(s) - comma-separated, e.g. K1,K2,K3")
        parser.add_argument("--file", help="Path to file containing keys (one key per line)")
        parser.add_argument("--raw", action="store_true", help="Show raw JSON")
        parser.add_argument(
            "--format", choices=["bibtex", "ris"], help="Export in specific bibliographic format"
        )
        parser.add_argument(
            "--full-notes", action="store_true", help="Show full content of child notes"
        )

    def execute(self, args: argparse.Namespace) -> None:
        import json

        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, "user", False))

        keys = []
        if args.key:
            keys.extend([k.strip() for k in args.key.split(",") if k.strip()])
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                keys.extend([line.strip() for line in f if line.strip()])

        if not keys:
            console.print("[bold red]Error: You must specify --key or --file.[/bold red]")
            return

        for idx, key in enumerate(keys):
            item = gateway.get_item(key)
            if not item:
                console.print(f"[bold red]Item '{key}' not found.[/bold red]")
                continue

            if len(keys) > 1:
                console.print(
                    f"\n[bold yellow]--- Inspecting Item {idx + 1}/{len(keys)}: {key} ---[/bold yellow]"
                )

            if args.raw:
                print(json.dumps(item.raw_data, indent=2))
                continue

            if args.format:
                export_service = GatewayFactory.get_export_service(
                    force_user=getattr(args, "user", False)
                )
                if args.format == "bibtex":
                    print(export_service.serialize_bibtex([item]))
                elif args.format == "ris":
                    print(export_service.serialize_ris([item]))
                continue

            # Resolve collections
            col_list = []
            for ckey in item.collections:
                c = gateway.get_collection(ckey)
                name = c.get("data", {}).get("name", ckey) if c else ckey
                col_list.append(f"{name} ({ckey})")
            collections_str = ", ".join(col_list) if col_list else "None"

            abstract_display = (
                item.abstract
                if item.abstract
                else "[blink bright_red]<no abstract>[/blink bright_red] ❗"
            )

            console.print(
                Panel(
                    f"[bold]Collections:[/bold] {collections_str}\n"
                    f"[bold]Title:[/bold] {item.title}\n"
                    f"[bold]Type:[/bold] {item.item_type}\n"
                    f"[bold]Date:[/bold] {item.date}\n"
                    f"[bold]Added:[/bold] {item.date_added}\n"
                    f"[bold]Modified:[/bold] {item.date_modified}\n"
                    f"[bold]Authors:[/bold] {', '.join(item.authors)}\n"
                    f"[bold]DOI:[/bold] {item.doi}\n"
                    f"[bold]URL:[/bold] {item.url}\n\n"
                    f"[bold]Abstract:[/bold]\n{abstract_display}",
                    title=f"Item: {key}",
                )
            )

            # Children (Notes/Attachments)
            children = gateway.get_item_children(key)
            if children:
                console.print(f"\n[bold]Children ({len(children)}):[/bold]")
                for child in children:
                    ctype = child.get("data", {}).get("itemType", "unknown")
                    ckey = str(child.get("key", ""))
                    cdata = child.get("data", {})
                    if ctype == "note":
                        note_full = cdata.get("note", "")
                        date_added = cdata.get("dateAdded", "N/A")
                        date_modified = cdata.get("dateModified", "N/A")

                        # Try to parse as JSON (handling common <div> wrapper)
                        is_json = False
                        raw_json = note_full
                        if note_full.startswith("<div>") and note_full.endswith("</div>"):
                            raw_json = note_full[5:-6].strip()

                        try:
                            parsed_data = json.loads(raw_json)
                            is_json = True
                        except (json.JSONDecodeError, TypeError):
                            parsed_data = None

                        if args.full_notes:
                            console.print(
                                f"  - [cyan]Note[/cyan] ({ckey}) [dim]Added: {date_added} | Mod: {date_modified}[/dim]"
                            )
                            if is_json:
                                from rich.json import JSON

                                console.print(Panel(JSON(raw_json), border_style="cyan"))
                            else:
                                console.print(Panel(note_full, border_style="cyan"))
                        else:
                            if is_json:
                                display_content = json.dumps(
                                    parsed_data, indent=2, ensure_ascii=False
                                )
                            else:
                                display_content = note_full

                            note_snippet = display_content[:150].replace("\n", " ")
                            console.print(
                                f"  - [cyan]Note[/cyan] ({ckey}) [dim]Added: {date_added} | Mod: {date_modified}[/dim]\n"
                                f"    {note_snippet}..."
                            )
                    else:
                        filename = cdata.get("filename", "N/A")
                        console.print(f"  - [green]Attachment[/green] ({ckey}): {filename}")


@CommandRegistry.register
class ItemCommand(BaseCommand):
    name = "item"
    help = "Paper/Item operations (move, inspect, delete, etc.)"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        sub = parser.add_subparsers(dest="verb", required=True)

        # Inspect
        inspect_p = sub.add_parser("inspect", help=InspectCommand.help)
        InspectCommand().register_args(inspect_p)

        # Move
        move_p = sub.add_parser(
            "move",
            help="Move item between collections",
            description="Moves a research item from one collection to another by updating its collection links in the Zotero library.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Categorizing a paper into a specific folder
Problem: I have a paper in "Incoming Search" (Key: INC_01) and I want to move it to my "Methodology" folder (Key: METH_01).
Action:  zotero-cli item move --item-id "ABCD1234" --source "INC_01" --target "METH_01"
Result:  The item is now correctly linked to the "Methodology" folder and removed from "Incoming Search."

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to move an item using a name for the source or target that corresponds to multiple collections. This will lead to an ambiguity error.
• Safety Tips: Always use item list or collection list to find the exact keys before moving critical items. Moving an item does not affect its metadata or attachments.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_move.md
""",
        )
        move_p.add_argument("--item-id", required=True)
        move_p.add_argument("--source", help="Source collection (optional if unambiguous)")
        move_p.add_argument("--target", required=True)

        # List (Subset of list items)
        list_p = sub.add_parser(
            "list",
            help="List items in a collection",
            description="Displays a table of research items within a collection, the trash, or unfiled at the library root. For filtering by screening decision (included/excluded), phase, or persona, use `slr list` instead.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Browsing everything in a folder
Problem: I want to see all items currently in my "Final Selection" folder (Key: FIN_01).
Action:  zotero-cli item list --collection "FIN_01"
Result:  The table displays every item in that collection, showing their titles and unique keys.

Scenario: Filtering by screening decision instead
Problem: I want only the items that were accepted, not everything in the folder.
Action:  zotero-cli slr list included --tree "FIN_01"
Result:  Only items with an 'Accepted' SDB audit note are shown.

Cognitive Safeguards
--------------------
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

        # Update
        update_p = sub.add_parser(
            "update",
            help="Update item metadata",
            description="Corrects or enhances the metadata of an individual Zotero item, including fields such as Title, DOI, and Abstract.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Correcting a title with typos
Problem: My paper with key ABCD1234 has a typo in the title: "Attension is all you need."
Action:  zotero-cli item update --key "ABCD1234" --title "Attention is All You Need"
Result:  The title is correctly updated in the Zotero library.

Cognitive Safeguards
--------------------
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
        update_p.add_argument(
            "--version", type=int, help="Current version (auto-resolved if omitted)"
        )

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
Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to fetch for an item without valid DOI metadata.
• Safety Tips: Use fetch as your first attempt for mass metadata enrichment.
""",
        )
        fetch_p.add_argument("--key", help=ITEM_KEY_HELP)
        fetch_p.add_argument("--collection", help="Fetch PDFs for all items in a collection")
        fetch_p.add_argument("--file", help="Fetch PDFs for all items in a key-list file")
        fetch_p.add_argument("--verbose", action="store_true")

        strip_p = pdf_sub.add_parser(
            "strip",
            help="Remove PDF attachments from a specific item",
            description="Permanently deletes all existing PDF attachments linked to the item from the Zotero library.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Cognitive Safeguards
--------------------
• Common Failure Modes: strip is irreversible and will permanently delete files from your Zotero storage.
""",
        )
        strip_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
        strip_p.add_argument("--execute", action="store_true", help="Actually perform deletions")
        strip_p.add_argument("--verbose", action="store_true")

        attach_p = pdf_sub.add_parser(
            "attach",
            help="Attach a local file to an item",
            description="Manually uploads a local file from your computer and links it as a child attachment to the item in Zotero.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Manually attaching a downloaded paper
Problem: I've manually downloaded a paper ("Manual_Ref.pdf") and want to attach it to its corresponding item (Key: REF_123) in Zotero.
Action:  zotero-cli item pdf attach "REF_123" --file "Manual_Ref.pdf"
Result:  The PDF is uploaded and linked to the item in the Zotero cloud storage.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attaching a file that is too large for your Zotero storage quota.
""",
        )
        attach_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
        attach_p.add_argument("--file", required=True, help="Path to local file")

        # Hydrate
        hydrate_p = sub.add_parser(
            "hydrate",
            help="Enrich metadata from external sources (e.g. ArXiv -> DOI)",
            description="Automatically enriches the metadata of items by retrieving missing fields (like DOIs, abstracts, and publication dates) from online sources.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Enriching a collection after an ArXiv import
Problem: I've imported 50 items from ArXiv, but many of them are missing their formal DOI identifiers and abstracts.
Action:  zotero-cli item hydrate --collection "ARXIV_FOLDER" --dry-run
Result:  The CLI shows a summary of which items can be updated with verified DOIs and dates from CrossRef.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting hydration for items that have no existing metadata (like unfiled PDF attachments). Hydration requires a baseline Title or Identifier to pivot.
• Safety Tips: Always use --dry-run when running on an entire collection to ensure updates are accurate.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_hydrate.md
""",
        )
        hydrate_p.add_argument("--key", help=ITEM_KEY_HELP)
        hydrate_p.add_argument("--collection", help="Hydrate all items in a collection")
        hydrate_p.add_argument(
            "--all", action="store_true", help="Scan entire library for hydration"
        )
        hydrate_p.add_argument(
            "--dry-run", action="store_true", help="Show changes without applying"
        )

        # Purge
        purge_p = sub.add_parser(
            "purge",
            help="Purge assets (files, notes, tags) from an item",
            description="Permanently removes specific types of child assets (PDFs, notes, or tags) from a research item without deleting the main bibliographic record itself.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Cleaning up annotations before a re-read
Problem: I have a paper (Key: READ_456) filled with old notes and tags that are no longer relevant to my current project.
Action:  zotero-cli item purge --key "READ_456" --notes --tags
Result:  All notes and tags are removed from the paper, providing a clean slate for new analysis.

Cognitive Safeguards
--------------------
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

        # Delete
        delete_p = sub.add_parser(
            "delete",
            help="Permanently delete an item",
            description="Permanently deletes a research item from the Zotero library. The Zotero Web API only exposes a hard, permanent DELETE - there is no soft-delete/trash-write path, so this cannot be undone.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Removing a genuine duplicate/junk record
Problem: I manually added a test item (Key: JUNK_01) by mistake and want it gone entirely.
Action:  zotero-cli item delete --key "JUNK_01"
Result:  The item is permanently removed from the library. This cannot be undone.

Cognitive Safeguards
--------------------
• Common Failure Modes: Assuming this moves the item to a recoverable trash - it does not, the Web API has no such mechanism.
• Safety Tips: ALWAYS verify the item key using item inspect before deleting. For consolidating duplicates instead of discarding one outright, use item merge.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_delete.md
""",
        )
        delete_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
        delete_p.add_argument(
            "--version", type=int, help="Current version (auto-resolved if omitted)"
        )

        # Trash
        trash_p = sub.add_parser(
            "trash",
            help="Move an item to the trash (--offline mode only)",
            description="Moves an item into Zotero's trash by writing directly to the local zotero.sqlite, replicating exactly what Zotero Desktop itself writes when you delete an item from its UI (bumps dateModified/clientDateModified, marks the row dirty so Desktop's next sync pushes the change to the server, adds a deletedItems row). Only supported in --offline mode: the Zotero Web API has no documented, reversible trash write, only a permanent DELETE - see `item delete`.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Cleaning up a duplicate found while working offline
Problem: I want to trash item ABCD1234 in my local library, the same as clicking delete in Zotero Desktop.
Action:  zotero-cli item trash --key "ABCD1234" --offline --execute
Result:  The item is moved to the trash in zotero.sqlite. It appears in Zotero Desktop's trash next time Desktop opens or syncs.

Cognitive Safeguards
--------------------
• Common Failure Modes: Running without --offline (not supported in online/API mode); running while Zotero Desktop is actively writing to the same file - fails cleanly with a lock error, just retry or close Desktop first.
• Safety Tips: Close Zotero Desktop first to avoid a database lock. Reversible via `item restore`, unless you also run Desktop's "Empty Trash".

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_trash.md
""",
        )
        trash_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
        trash_p.add_argument(
            "--execute", action="store_true", help="Actually perform the write (default: preview only)"
        )
        trash_p.add_argument(
            "--force", action="store_true", help="Skip the interactive confirmation prompt"
        )

        # Restore
        restore_p = sub.add_parser(
            "restore",
            help="Restore an item from the trash (--offline mode only)",
            description="Restores a trashed item by writing directly to the local zotero.sqlite, replicating exactly what Zotero Desktop itself writes when you restore an item from its trash (bumps dateModified/clientDateModified, marks the row dirty so Desktop's next sync pushes the change to the server, removes the deletedItems row). Only supported in --offline mode. Does not undo any prior `item merge` relations left on the item - a narrow edge case left untouched rather than guessed at.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Undoing an accidental trash
Problem: I ran `item trash --key ABCD1234 --execute` by mistake and want it back.
Action:  zotero-cli item restore --key "ABCD1234" --offline --execute
Result:  The item is removed from the trash in zotero.sqlite and appears normally again in Zotero Desktop.

Cognitive Safeguards
--------------------
• Common Failure Modes: Running without --offline (not supported in online/API mode); trying to restore an item Desktop's "Empty Trash" already permanently deleted - restore only works before that point.
• Safety Tips: Close Zotero Desktop first to avoid a database lock.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_restore.md
""",
        )
        restore_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
        restore_p.add_argument(
            "--execute", action="store_true", help="Actually perform the write (default: preview only)"
        )
        restore_p.add_argument(
            "--force", action="store_true", help="Skip the interactive confirmation prompt"
        )

        # Transfer
        transfer_p = sub.add_parser(
            "transfer",
            help="Transfer item between different libraries",
            description="Copies or moves a research item (including its metadata and PDF attachments) from your personal library to a Zotero group library, or between different groups.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Moving a paper to a shared project group
Problem: I've found a perfect paper in my personal library and I want to share it with my lab's Zotero group (ID: 987654).
Action:  zotero-cli item transfer --key "ABCD1234" --target-group "987654"
Result:  A duplicate of the paper and its PDF is created in the lab's group library.

Cognitive Safeguards
--------------------
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

        # Export
        export_p = sub.add_parser(
            "export",
            help="Export item metadata or content",
            description="Exports the metadata of a single Zotero item into standard formats (bibtex, ris, or md), either to a local file or directly to the terminal output.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Getting a BibTeX entry for a specific citation
Problem: I'm writing a paper and I just need the BibTeX code for the item with key VA12345.
Action:  zotero-cli item export --key "VA12345" --format bibtex
Result:  The CLI prints the formatted BibTeX entry directly to the terminal.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to export an item key that doesn't exist or for which metadata is incomplete.
• Safety Tips: Use the md format to generate a local Markdown "Digital Twin" of your Zotero item.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_export.md
""",
        )
        export_p.add_argument("--key", required=True, help=ITEM_KEY_HELP)
        export_p.add_argument(
            "--format", default="bibtex", choices=["bibtex", "ris", "md"], help="Export format"
        )
        export_p.add_argument("--output", help="Output file path or directory (for md)")

        # Add
        add_p = sub.add_parser(
            "add",
            help="Manually add a new item to a collection",
            description="Manually creates a new research item in a specific Zotero collection by providing core bibliographic fields directly from the terminal.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Manually adding an internal technical report
Problem: I have a PDF of an internal company report that isn't online and I want to add it to my "References" folder (Key: REF_01).
Action:  zotero-cli item add --title "Advanced RAG Pipelines V2" --authors "Engineering Team" --collection "REF_01" --type report
Result:  A new item of type "report" is created in Zotero, ready for PDF attachment.

Cognitive Safeguards
--------------------
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
        add_p.add_argument(
            "--authors", help="Comma-separated authors (e.g. 'John Doe, Jane Smith')"
        )
        add_p.add_argument("--date", help="Publication Date")
        add_p.add_argument("--abstract", help="Abstract/Note")

        # Merge
        merge_p = sub.add_parser(
            "merge",
            help="Merge duplicate items into one survivor",
            description="Merges one or more duplicate items into a chosen master: unions tags and collection membership, moves notes/attachments onto the master, then permanently deletes the (now emptied) duplicates. Use `report duplicates` first to find candidate keys, or `report duplicates --export-plan` for a bulk-editable plan file.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Consolidating a paper imported twice from different search databases
Problem: report duplicates found the same paper as items IEEE_KEY1 (master, more complete) and SPR_KEY2 (duplicate).
Action:  zotero-cli item merge --master "IEEE_KEY1" --duplicates "SPR_KEY2" --execute
Result:  SPR_KEY2's tags, collections, notes, and attachments move onto IEEE_KEY1; SPR_KEY2 is permanently deleted.

Scenario: Previewing a merge before committing
Problem: I want to see what a merge would do without touching my library yet.
Action:  zotero-cli item merge --master "IEEE_KEY1" --duplicates "SPR_KEY2"
Result:  A preview table is shown (tags/collections to add, notes/attachments to move); nothing is written since --execute was omitted.

Scenario: Bulk-resolving a batch of duplicate groups from a plan file
Problem: I exported duplicates.csv via `report duplicates --export-plan`, filled in the role/reason columns for every group, and want to commit them all at once.
Action:  zotero-cli item merge --from-plan duplicates.csv --execute
Result:  Every fully-resolved group is merged in one pass; if any group is still missing a decision, nothing is written and the incomplete groups are listed.

Cognitive Safeguards
--------------------
• Common Failure Modes: Master and duplicates must share the same item type - Zotero Desktop enforces the same rule. Conflicting scalar fields (title, date, DOI, ISBN, URL, abstract) must be resolved interactively (single-group form) before --execute can proceed; there is no silent "first wins" default. With --from-plan, an incomplete plan (any group missing a decision) blocks the entire batch, not just that group.
• Safety Tips: This is PERMANENT - the Zotero Web API only supports hard delete, there is no undo the way Zotero Desktop's internal merge has. Run without --execute first to preview. Any citation-management document referencing a duplicate's key by that key will break.

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
            "--execute", action="store_true", help="Actually perform the merge (default: preview only)"
        )
        merge_p.add_argument("--force", action="store_true", help="Skip the confirmation prompt")

    def execute(self, args: argparse.Namespace) -> None:
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        if args.verb == "inspect":
            InspectCommand().execute(args)
        elif args.verb == "move":
            self._handle_move(args)
        elif args.verb == "list":
            self._handle_list(gateway, args)
        elif args.verb == "update":
            self._handle_update(gateway, args)
        elif args.verb == "delete":
            self._handle_delete(gateway, args)
        elif args.verb == "trash":
            self._handle_trash(gateway, args)
        elif args.verb == "restore":
            self._handle_restore(gateway, args)
        elif args.verb == "pdf":
            self._handle_pdf_ops(args)
        elif args.verb == "hydrate":
            self._handle_hydrate(args)
        elif args.verb == "purge":
            self._handle_purge(args)
        elif args.verb == "transfer":
            self._handle_transfer(args)
        elif args.verb == "export":
            self._handle_export(args)
        elif args.verb == "add":
            self._handle_add(gateway, args)
        elif args.verb == "merge":
            self._handle_merge(args)

    def _handle_merge(self, args: argparse.Namespace) -> None:
        if getattr(args, "from_plan", None):
            self._handle_merge_from_plan(args)
            return

        if not args.master or not args.duplicates:
            console.print(
                "[red]Error: Provide either (--master and --duplicates) or --from-plan.[/red]"
            )
            return

        from rich.prompt import Confirm, Prompt

        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_merge_service(force_user=force_user)

        master_key = args.master
        duplicate_keys = [k.strip() for k in args.duplicates.split(",") if k.strip()]

        conflicts = service.detect_conflicts(master_key, duplicate_keys)
        field_resolutions: dict = {}
        if conflicts:
            console.print(
                f"[yellow]{len(conflicts)} conflicting field(s) need an explicit resolution:[/yellow]"
            )
            for conflict in conflicts:
                console.print(f"  [bold]{conflict.field_name}[/bold]:")
                for key, value in conflict.values.items():
                    console.print(f"    {key}: {value!r}")
                choices = [v for v in conflict.values.values() if v]
                field_resolutions[conflict.field_name] = Prompt.ask(
                    f"  Value to keep for '{conflict.field_name}'",
                    choices=choices,
                    default=choices[0],
                )

        # Always preview first, regardless of --execute: this both shows the
        # user what will happen and surfaces unresolved-conflict errors
        # before any write is attempted.
        preview = service.merge(
            master_key, duplicate_keys, field_resolutions=field_resolutions, dry_run=True
        )

        if not preview.success:
            for error in preview.errors:
                console.print(f"[red]Error:[/red] {error}")
            return

        table = Table(title="Merge Preview")
        table.add_column("Field")
        table.add_column("Value")
        table.add_row("Master", preview.master_key)
        table.add_row("Duplicates", ", ".join(duplicate_keys))
        table.add_row("Tags to add", str(preview.tags_added))
        table.add_row("Collections to add", str(preview.collections_added))
        table.add_row("Notes to move", str(preview.notes_moved))
        table.add_row("Attachments to move", str(preview.attachments_moved))
        if preview.field_resolutions_applied:
            table.add_row("Field resolutions", str(preview.field_resolutions_applied))
        console.print(table)

        if not args.execute:
            console.print(
                "[yellow]Preview only - nothing was written. This merge is PERMANENT and "
                "cannot be undone once run with --execute (the Zotero Web API only supports "
                "hard delete). Re-run with --execute to apply.[/yellow]"
            )
            return

        if not args.force:
            console.print(
                f"[yellow]About to permanently delete {len(duplicate_keys)} item(s) after "
                "moving their notes/attachments to the master. This cannot be undone.[/yellow]"
            )
            if not Confirm.ask("Proceed?"):
                console.print(ABORTED_NO_WRITES_MSG)
                return

        result = service.merge(
            master_key, duplicate_keys, field_resolutions=field_resolutions, dry_run=False
        )
        for error in result.errors:
            console.print(f"[red]Warning:[/red] {error}")
        if result.success:
            console.print(
                f"[green]Merged {len(result.merged_keys)} duplicate(s) into "
                f"'{result.master_key}'.[/green]"
            )
        else:
            console.print("[red]Merge did not complete successfully - see warnings above.[/red]")

    def _handle_merge_from_plan(self, args: argparse.Namespace) -> None:
        from pathlib import Path

        from rich.prompt import Confirm

        from zotero_cli.core.services.merge_plan_io import parse_plan_from_csv, parse_plan_from_json

        path = Path(args.from_plan)
        if not path.exists():
            console.print(f"[red]Error: Plan file '{path}' not found.[/red]")
            return

        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            plan = parse_plan_from_json(text)
        else:
            plan = parse_plan_from_csv(text)

        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_merge_service(force_user=force_user)

        # Always preview first, regardless of --execute: surfaces incomplete
        # groups before any write is attempted, and shows what would happen.
        preview = service.execute_plan(plan, dry_run=True)

        table = Table(title="Merge Plan Preview")
        table.add_column("Group")
        table.add_column("Status")
        table.add_column("Master")
        table.add_column("Merge Keys")
        table.add_column("Reason")
        for entry in plan.entries:
            if entry.decision is None:
                table.add_row(entry.group_id, "[yellow]UNRESOLVED[/yellow]", "-", "-", "-")
            else:
                table.add_row(
                    entry.group_id,
                    "[green]resolved[/green]",
                    entry.decision.master_key,
                    ", ".join(entry.decision.merge_keys) or "(none - kept as-is)",
                    entry.decision.reason,
                )
        console.print(table)

        if not preview.success:
            console.print(
                "[red]Plan is incomplete - nothing will be written until every group has a "
                "decision:[/red]"
            )
            for error in preview.errors:
                console.print(f"  [red]{error}[/red]")
            return

        if not args.execute:
            console.print(
                "[yellow]Preview only - nothing was written. This merge is PERMANENT and "
                "cannot be undone once run with --execute. Re-run with --execute to apply.[/yellow]"
            )
            return

        if not args.force:
            groups_with_merges = sum(1 for e in plan.entries if e.decision and e.decision.merge_keys)
            console.print(
                f"[yellow]About to execute {groups_with_merges} merge(s) from this plan. "
                "This cannot be undone.[/yellow]"
            )
            if not Confirm.ask("Proceed?"):
                console.print(ABORTED_NO_WRITES_MSG)
                return

        result = service.execute_plan(plan, dry_run=False)
        for group_result in result.group_results:
            for error in group_result.errors:
                console.print(f"[red]Warning ({group_result.master_key}):[/red] {error}")
        succeeded = sum(1 for g in result.group_results if g.success)
        console.print(
            f"[green]Merged {succeeded}/{len(result.group_results)} group(s) from the plan.[/green]"
            if result.success
            else "[red]Plan execution did not fully succeed - see warnings above.[/red]"
        )

    def _handle_list(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        if getattr(args, "trash", False):
            items = list(gateway.get_trash_items())
            title = "Trash Items"
        elif getattr(args, "root", False):
            items = list(gateway.get_orphan_items(top_only=getattr(args, "top_only", False)))
            title = "Root/Orphan Items (unfiled)"
        else:
            if not getattr(args, "collection", None):
                console.print(
                    "[red]Error: --collection or --root required for non-trash listings.[/red]"
                )
                return
            col_id = gateway.get_collection_id_by_name(args.collection)
            if not col_id:
                col_id = args.collection  # Try Key

            items = list(
                gateway.get_items_in_collection(col_id, top_only=getattr(args, "top_only", False))
            )
            title = f"Items in {args.collection}"

        table = Table(title=title)
        table.add_column("Key", style="cyan")
        table.add_column("Title")
        table.add_column("Type")
        for item in items:
            table.add_row(item.key, item.title or "Untitled", item.item_type)

        console.print(table)
        console.print(f"\n[dim]Showing {len(items)} items.[/dim]")

    def _handle_transfer(self, args: argparse.Namespace) -> None:
        from dataclasses import replace

        from zotero_cli.core.config import get_config

        source_gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, "user", False))

        config = get_config()
        # Create a modified config for the destination (Target is always a group in this command)
        dest_config = replace(config, library_id=args.target_group, library_type="group")
        dest_gateway = GatewayFactory.get_zotero_gateway(config=dest_config, force_user=False)

        service = GatewayFactory.get_transfer_service()

        print(f"Transferring item {args.key} to group {args.target_group}...")
        new_key = service.transfer_item(
            args.key, source_gateway, dest_gateway, delete_source=args.delete_source
        )

        if new_key:
            print(f"Transfer complete. New key in destination: {new_key}")
        else:
            print("Transfer failed.", file=sys.stderr)
            sys.exit(1)

    def _handle_purge(self, args: argparse.Namespace) -> None:
        from rich.prompt import Confirm

        types = []
        if args.files:
            types.append("files")
        if args.notes:
            types.append("notes")
        if args.tags:
            types.append("tags")

        if not types:
            console.print("[red]Error: Specify what to purge using --files, --notes, or --tags.[/]")
            return

        if not args.force:
            msg = f"Are you sure you want to purge {', '.join(types)} from item '{args.key}'?"
            if not Confirm.ask(msg):
                console.print("[yellow]Aborted.[/]")
                return

        service = GatewayFactory.get_purge_service(force_user=getattr(args, "user", False))
        stats = service.purge_item_assets(args.key, types=types, dry_run=False)

        console.print(
            f"[green]Purge Complete:[/green] Deleted: {stats['deleted']}, Errors: {stats['errors']}"
        )

    def _handle_hydrate(self, args: argparse.Namespace) -> None:
        from rich.table import Table

        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_enrichment_service(force_user=force_user)

        results = []
        if args.key:
            res = service.hydrate_item(args.key, dry_run=args.dry_run)
            if res:
                results.append(res)
        elif args.collection:
            print(f"Hydrating collection '{args.collection}'...")
            results = service.hydrate_collection(args.collection, dry_run=args.dry_run)
        elif args.all:
            print("Hydrating entire library (ArXiv items)...")
            results = service.hydrate_all(dry_run=args.dry_run)
        else:
            print("Error: Specify an item Key, --collection, or --all.")
            return

        if not results:
            print("No items needed hydration.")
            return

        table = Table(title="Hydration Report" + (" (DRY RUN)" if args.dry_run else ""))
        table.add_column("Key")
        table.add_column("Title", overflow="fold")
        table.add_column("Old DOI")
        table.add_column("New DOI")
        table.add_column("New Journal")

        for r in results:
            table.add_row(
                r["key"],
                r["title"],
                r["old_doi"],
                r["new_doi"],
                r["new_journal"],
            )

        console.print(table)
        print(f"\nTotal items hydrated: {len(results)}")

    def _handle_pdf_ops(self, args: argparse.Namespace) -> None:
        force_user = getattr(args, "user", False)
        if args.pdf_verb == "fetch":
            gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
            pdf_finder = GatewayFactory.get_pdf_finder_service(force_user=force_user)

            keys = []
            if args.key:
                keys.append(args.key)

            if args.collection:
                col_id = gateway.get_collection_id_by_name(args.collection)
                if col_id:
                    items = gateway.get_items_in_collection(col_id)
                    keys.extend([i.key for i in items])
                else:
                    console.print(f"[red]Error: Collection '{args.collection}' not found.[/red]")
                    return

            if args.file:
                import os

                if not os.path.exists(args.file):
                    console.print(f"[red]Error: File '{args.file}' not found.[/red]")
                    return
                with open(args.file, "r") as f:
                    keys.extend([line.strip() for line in f if line.strip()])

            if not keys:
                console.print("[red]Error: Provide a key, --collection, or --file.[/red]")
                return

            # Deduplicate
            unique_keys = []
            seen = set()
            for k in keys:
                if k not in seen:
                    unique_keys.append(k)
                    seen.add(k)

            # Enqueue all
            for k in unique_keys:
                jid = pdf_finder.enqueue_find_pdf(k)
                if args.verbose:
                    console.print(f"Enqueued discovery job {jid} for item {k}")

            console.print(
                f"[bold]Starting resilient PDF discovery for {len(unique_keys)} items...[/bold]"
            )
            asyncio.run(pdf_finder.process_jobs())
            console.print("[bold green]Discovery workers finished.[/bold green]")

        elif args.pdf_verb == "strip":
            purge_service = GatewayFactory.get_purge_service(force_user=force_user)
            dry_run = not args.execute
            stats = purge_service.purge_item_assets(args.key, dry_run=dry_run)
            count = stats["deleted"] if not dry_run else stats["skipped"]
            if dry_run:
                print(
                    f"[yellow]DRY RUN:[/yellow] Would remove {count} attachments from {args.key}."
                )
            else:
                print(f"Removed {count} attachments from {args.key}.")
        elif args.pdf_verb == "attach":
            gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
            self._handle_pdf_attach(gateway, args)

    def _handle_pdf_attach(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        import mimetypes
        import os

        path = args.file
        if not os.path.exists(path):
            print(f"Error: File not found: {path}")
            return

        mime_type, _ = mimetypes.guess_type(path)
        mime_type = mime_type or "application/octet-stream"

        print(f"Attaching local file: {path} (MIME: {mime_type})")
        if gateway.upload_attachment(args.key, path, mime_type=mime_type):
            print("Successfully attached file.")
        else:
            print("Failed to attach file.")

    def _handle_delete(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        version = args.version
        if version is None:
            item = gateway.get_item(args.key)
            if not item:
                print(f"Error: Item {args.key} not found.")
                return
            version = item.version

        if gateway.delete_item(args.key, version):
            print(f"Deleted item {args.key} successfully.")
        else:
            print(f"Failed to delete item {args.key}.")

    def _handle_trash(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

        if not isinstance(gateway, SqliteZoteroGateway):
            console.print(
                "[red]Error:[/red] `item trash` currently only supports [bold]--offline[/bold] "
                "mode. The Zotero Web API has no documented, reversible trash write - only a "
                "permanent DELETE (see `item delete`)."
            )
            return

        item = gateway.get_item(args.key)
        if not item:
            console.print(f"[bold red]Item '{args.key}' not found.[/bold red]")
            return

        if not args.execute:
            console.print(
                f"[yellow]Preview only[/yellow] - would move '[cyan]{item.title}[/cyan]' "
                f"([magenta]{args.key}[/magenta]) to the trash in zotero.sqlite. Re-run with "
                "--execute to apply."
            )
            return

        if not args.force:
            from rich.prompt import Confirm

            console.print(
                "[yellow]This writes directly to your local zotero.sqlite, the same file "
                "Zotero Desktop reads. Close Desktop first to avoid a database lock.[/yellow]"
            )
            if not Confirm.ask(f"Move '{item.title}' ({args.key}) to trash?"):
                console.print(ABORTED_NO_WRITES_MSG)
                return

        if gateway.trash_item(args.key):
            console.print(f"[bold green]Moved to trash:[/bold green] {args.key}")
        else:
            console.print(f"[bold red]Failed to trash item {args.key}.[/bold red]")

    def _handle_restore(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

        if not isinstance(gateway, SqliteZoteroGateway):
            console.print(
                "[red]Error:[/red] `item restore` currently only supports [bold]--offline[/bold] "
                "mode."
            )
            return

        item = gateway.get_item(args.key)
        if not item:
            console.print(f"[bold red]Item '{args.key}' not found.[/bold red]")
            return

        if not args.execute:
            console.print(
                f"[yellow]Preview only[/yellow] - would restore '[cyan]{item.title}[/cyan]' "
                f"([magenta]{args.key}[/magenta]) from the trash in zotero.sqlite. Re-run with "
                "--execute to apply."
            )
            return

        if not args.force:
            from rich.prompt import Confirm

            console.print(
                "[yellow]This writes directly to your local zotero.sqlite, the same file "
                "Zotero Desktop reads. Close Desktop first to avoid a database lock.[/yellow]"
            )
            if not Confirm.ask(f"Restore '{item.title}' ({args.key}) from trash?"):
                console.print(ABORTED_NO_WRITES_MSG)
                return

        if gateway.restore_item(args.key):
            console.print(f"[bold green]Restored from trash:[/bold green] {args.key}")
        else:
            console.print(f"[bold red]Failed to restore item {args.key}.[/bold red]")

    def _handle_update(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        import json

        payload = {}
        if args.json:
            payload = json.loads(args.json)

        if args.doi:
            payload["DOI"] = args.doi
        if args.title:
            payload["title"] = args.title
        if args.abstract:
            payload["abstractNote"] = args.abstract

        if not payload:
            print("Error: No updates provided. Use --doi, --title, --abstract, or --json.")
            return

        version = args.version
        if version is None:
            item = gateway.get_item(args.key)
            if not item:
                print(f"Error: Item {args.key} not found.")
                return
            version = item.version

        if gateway.update_item(args.key, version, payload):
            print(f"Updated item {args.key} successfully.")
        else:
            print(f"Failed to update item {args.key}.")

    def _handle_move(self, args: argparse.Namespace) -> None:
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_collection_service(force_user=force_user)
        if service.move_item(args.source, args.target, args.item_id):
            source_display = args.source or "auto"
            target_display = args.target
            if target_display.lower() in ["/", "root", "unfiled"]:
                target_display = "Root (Unfiled Items)"
            if source_display.lower() in ["/", "root", "unfiled"]:
                source_display = "Root (Unfiled Items)"

            print(f"Moved item {args.item_id} from {source_display} to {target_display}.")
        else:
            print("Failed to move item.")

    def _handle_export(self, args: argparse.Namespace) -> None:
        from pathlib import Path

        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        item = gateway.get_item(args.key)
        if not item:
            console.print(f"[bold red]Error:[/bold red] Item '{args.key}' not found.")
            return

        if args.format == "md":
            attach_service = GatewayFactory.get_attachment_service(force_user=force_user)
            output_dir = Path(args.output) if args.output else Path("./export_md")
            output_dir.mkdir(parents=True, exist_ok=True)

            console.print(f"Exporting full-text for: [cyan]{item.title}[/cyan]...")
            stats = attach_service.bulk_export_markdown([item], output_dir)

            if stats["success"] > 0:
                console.print(f"[bold green]Success![/bold green] Markdown saved to {output_dir}")
            elif stats["skipped"] > 0:
                console.print("[yellow]Skipped:[/yellow] Item has no PDF attachment.")
            else:
                console.print("[bold red]Failed:[/bold red] Could not extract text from PDF.")
        else:
            # BibTeX / RIS
            if not args.output:
                console.print("[red]Error: --output required for metadata export.[/red]")
                return

            export_service = GatewayFactory.get_export_service(force_user=force_user)
            console.print(
                f"Exporting item [cyan]{args.key}[/cyan] to [green]{args.output}[/green] ({args.format})..."
            )
            if export_service.export_items([item], args.output, args.format):
                console.print("[bold green]Export complete.[/bold green]")
            else:
                console.print("[bold red]Export failed.[/bold red]")

    def _handle_add(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        # 1. Resolve Collection
        col_id = gateway.get_collection_id_by_name(args.collection)
        if not col_id:
            col_id = args.collection  # Try as Key

        # 2. Get Template
        template = gateway.get_item_template(args.type)
        if not template:
            console.print(
                f"[bold red]Error:[/bold red] Could not fetch template for type '{args.type}'."
            )
            return

        # 3. Populate Template
        template["title"] = args.title
        template["collections"] = [col_id]

        if args.abstract:
            # Zotero uses abstractNote for most items
            if "abstractNote" in template:
                template["abstractNote"] = args.abstract
            elif "note" in template:
                template["note"] = args.abstract

        if args.date and "date" in template:
            template["date"] = args.date

        if args.authors and "creators" in template:
            creators = []
            author_list = [a.strip() for i, a in enumerate(args.authors.split(",")) if a.strip()]
            for author in author_list:
                parts = author.rsplit(" ", 1)
                if len(parts) == 2:
                    creators.append(
                        {"creatorType": "author", "firstName": parts[0], "lastName": parts[1]}
                    )
                else:
                    creators.append({"creatorType": "author", "name": author})
            template["creators"] = creators

        # 4. Create Item
        console.print(f"Creating new [cyan]{args.type}[/cyan]: [bold]{args.title}[/bold]...")
        new_key = gateway.create_generic_item(template)

        if new_key:
            console.print(
                f"[bold green]Success![/bold green] Item created with key: [magenta]{new_key}[/magenta]"
            )
        else:
            console.print("[bold red]Error:[/bold red] Failed to create item.")

