import argparse
import sys

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.flags import add_details_flag, add_key_argument, add_renamed_flag, resolve_key
from zotero_cli.cli.presenters import item_list_presenter
from zotero_cli.cli.safety import warn_default_apply
from zotero_cli.core.exceptions import NotFound, UsageError, ZoteroCliError
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.utils.sdb_parser import decode_json_note
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.utils.terminal_safety import safe_markup, strip_controls
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
Examples
--------
Scenario: Verifying metadata after an import
Problem: I've imported a paper and want to ensure the DOI was correctly captured and check for any existing notes.
Action:  zotero-cli item inspect --key "ABCD1234"
Result:  The CLI displays a detailed view of the item, including its DOI, abstract, and list of child PDF attachments.

Notes
-----
• Common Failure Modes: Attempting to inspect an item key that does not exist or for which you lack read permissions.
• Safety Tips: Use item list or search to find the correct key if you are unsure. For very large notes, the --full-notes flag may result in a lot of terminal scroll.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_inspect.md
"""
        add_key_argument(parser, "Zotero Item Key(s) - comma-separated, e.g. K1,K2,K3", required=False)
        parser.add_argument("--file", help="Path to file containing keys (one key per line)")
        parser.add_argument("--raw", action="store_true", help="Show raw JSON")
        add_renamed_flag(
            parser,
            "--as",
            "--format",
            dest="export_format",
            choices=["bibtex", "ris"],
            help="Export in a specific bibliographic format (--format is a deprecated alias)",
        )
        parser.add_argument(
            "--full-notes", action="store_true", help="Show full content of child notes"
        )

    def execute(self, args: argparse.Namespace) -> None:
        import json

        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, "user", False))

        resolve_key(args)
        keys = []
        if args.key:
            keys.extend([k.strip() for k in args.key.split(",") if k.strip()])
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                keys.extend([line.strip() for line in f if line.strip()])

        if not keys:
            raise UsageError("You must specify --key or --file.")

        missing: list[str] = []
        for idx, key in enumerate(keys):
            item = gateway.get_item(key)
            if not item:
                missing.append(key)
                continue

            if len(keys) > 1:
                console.print(
                    f"\n[bold yellow]--- Inspecting Item {idx + 1}/{len(keys)}: {safe_markup(key)} ---[/bold yellow]"
                )

            if args.raw:
                print(json.dumps(item.raw_data, indent=2))
                continue

            if args.export_format:
                export_service = GatewayFactory.get_export_service(
                    force_user=getattr(args, "user", False)
                )
                # Library fields go to the terminal as-is in these formats:
                # remove control characters (GHSA-3r38-p632-f79q).
                if args.export_format == "bibtex":
                    print(strip_controls(export_service.serialize_bibtex([item])))
                elif args.export_format == "ris":
                    print(strip_controls(export_service.serialize_ris([item])))
                continue

            # Resolve collections
            col_list = []
            for ckey in item.collections:
                c = gateway.get_collection(ckey)
                name = c.get("data", {}).get("name", ckey) if c else ckey
                col_list.append(f"{name} ({ckey})")
            collections_str = ", ".join(col_list) if col_list else "None"

            abstract_display = (
                safe_markup(item.abstract)
                if item.abstract
                # Plain ASCII, not an emoji glyph: Rich's legacy-Windows
                # renderer writes through the console's codepage (often
                # cp1252), which can't encode arbitrary Unicode and crashed
                # here (found by the #399 release smoke test).
                else "[blink bright_red]<no abstract>[/blink bright_red]"
            )

            console.print(
                Panel(
                    f"[bold]Collections:[/bold] {safe_markup(collections_str)}\n"
                    f"[bold]Title:[/bold] {safe_markup(item.title)}\n"
                    f"[bold]Type:[/bold] {safe_markup(item.item_type)}\n"
                    f"[bold]Date:[/bold] {safe_markup(item.date)}\n"
                    f"[bold]Added:[/bold] {safe_markup(item.date_added)}\n"
                    f"[bold]Modified:[/bold] {safe_markup(item.date_modified)}\n"
                    f"[bold]Authors:[/bold] {safe_markup(', '.join(item.authors))}\n"
                    f"[bold]DOI:[/bold] {safe_markup(item.doi)}\n"
                    f"[bold]URL:[/bold] {safe_markup(item.url)}\n\n"
                    f"[bold]Abstract:[/bold]\n{abstract_display}",
                    title=f"Item: {safe_markup(key)}",
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

                        # JSON notes (SDB, extraction) are HTML-escaped JSON in a <div>.
                        parsed_data = decode_json_note(note_full)
                        is_json = parsed_data is not None
                        raw_json = json.dumps(parsed_data) if is_json else note_full

                        if args.full_notes:
                            console.print(
                                f"  - [cyan]Note[/cyan] ({safe_markup(ckey)}) [dim]Added: {date_added} | Mod: {safe_markup(date_modified)}[/dim]"
                            )
                            if is_json:
                                from rich.json import JSON

                                console.print(Panel(JSON(raw_json), border_style="cyan"))
                            else:
                                console.print(Panel(safe_markup(note_full), border_style="cyan"))
                        else:
                            if is_json:
                                display_content = json.dumps(
                                    parsed_data, indent=2, ensure_ascii=False
                                )
                            else:
                                display_content = note_full

                            note_snippet = display_content[:150].replace("\n", " ")
                            console.print(
                                f"  - [cyan]Note[/cyan] ({safe_markup(ckey)}) [dim]Added: {date_added} | Mod: {safe_markup(date_modified)}[/dim]\n"
                                f"    {escape(note_snippet)}..."
                            )
                    else:
                        filename = cdata.get("filename") or "N/A"
                        console.print(f"  - [green]Attachment[/green] ({safe_markup(ckey)}): {escape(filename)}")

        if missing:
            # Shown items first, then a non-zero exit naming the rest (#368).
            raise NotFound(f"Item(s) not found: {', '.join(missing)}")


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
        add_renamed_flag(move_p, "--key", "--item-id", required=True, dest="key", help="Key of the item to move")
        move_p.add_argument("--source", help="Source collection (optional if unambiguous)")
        move_p.add_argument("--target", required=True, help="Destination collection name or key")

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

Scenario: Filtering by screening decision instead
Problem: I want only the items that were accepted, not everything in the folder.
Action:  zotero-cli slr list included --tree "FIN_01"
Result:  Only items with an 'Accepted' SDB audit note are shown.

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
            choices=["table", "json", "csv", "markdown"],
            default="table",
            help="Output format (Default: table)",
        )

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

        # Delete
        delete_p = sub.add_parser(
            "delete",
            help="Permanently delete an item",
            description="Permanently deletes a research item from the Zotero library, which cannot be undone - unless you pass --trash, which moves it to Zotero's trash instead (recoverable with `item restore`).",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples
--------
Scenario: Removing a genuine duplicate/junk record
Problem: I manually added a test item (Key: JUNK_01) by mistake and want it gone entirely.
Action:  zotero-cli item delete --key "JUNK_01" --execute
Result:  The item is permanently removed from the library. This cannot be undone.

Scenario: Deleting in a way I can undo
Problem: I want the item gone from my library view but not lost for good.
Action:  zotero-cli item delete --key "JUNK_01" --trash --execute
Result:  The item is in Zotero's trash (and Desktop's); `item restore --key "JUNK_01" --execute` brings it back.

Scenario: Checking what a delete would remove before committing to it
Problem: I want to see the item and its attachments/notes before deleting it.
Action:  zotero-cli item delete --key "JUNK_01" --dry-run
Result:  The item and its children are listed; nothing is deleted.

Notes
-----
• Common Failure Modes: Assuming this moves the item to a recoverable trash - it does not unless you pass --trash (that, or `item trash`, is what to use when in doubt).
• Safety Tips: ALWAYS verify the item key using item inspect before deleting. For consolidating duplicates instead of discarding one outright, use item merge.
• Deprecation: omitting both --dry-run and --execute still deletes immediately (for now) but prints a warning; pass --execute explicitly. This becomes preview-by-default in 4.0 (Issue #378).

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
            help="Move the item to Zotero's trash (recoverable) instead of deleting it permanently",
        )
        delete_mode = delete_p.add_mutually_exclusive_group()
        delete_mode.add_argument(
            "--execute", action="store_true", help="Delete the item (default for now; see Deprecation note)"
        )
        delete_mode.add_argument(
            "--dry-run", action="store_true", help="Preview the item and its children without deleting"
        )

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
            "--execute", action="store_true", help="Actually perform the write (default: preview only)"
        )
        trash_p.add_argument(
            "--force", action="store_true", help="Skip the interactive confirmation prompt"
        )

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
• Common Failure Modes: trying to restore an item that was permanently deleted (`item delete` without --trash, or Desktop's "Empty Trash") - restore only works before that point; the item changed on the server since it was read (the command fails and restores nothing - run it again).
• Safety Tips: With --offline, close Desktop first to avoid a database lock.

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
            help="With --delete-source: move the source item to Zotero's trash (recoverable) instead of deleting it permanently",
        )

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
        add_renamed_flag(
            export_p,
            "--as",
            "--format",
            dest="export_format",
            choices=["bibtex", "ris", "md"],
            default="bibtex",
            help="Export type (--format is a deprecated alias: it means output rendering elsewhere)",
        )
        export_p.add_argument("--output", help="Output file path or directory (for md)")

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
        add_p.add_argument(
            "--authors", help="Comma-separated authors (e.g. 'John Doe, Jane Smith')"
        )
        add_p.add_argument("--date", help="Publication Date")
        add_p.add_argument("--abstract", help="Abstract/Note")

        # Merge
        merge_p = sub.add_parser(
            "merge",
            help="Merge duplicate items into one survivor",
            description="Merges one or more duplicate items into a chosen master: unions tags and collection membership, moves notes/attachments onto the master, then permanently deletes the (now emptied) duplicates - or, with --trash, moves them to Zotero's trash so the merge can be undone. Use `report duplicates` first to find candidate keys, or `report duplicates --export-plan` for a bulk-editable plan file.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples
--------
Scenario: Consolidating a paper imported twice from different search databases
Problem: report duplicates found the same paper as items IEEE_KEY1 (master, more complete) and SPR_KEY2 (duplicate).
Action:  zotero-cli item merge --master "IEEE_KEY1" --duplicates "SPR_KEY2" --execute
Result:  SPR_KEY2's tags, collections, notes, and attachments move onto IEEE_KEY1; SPR_KEY2 is permanently deleted.

Scenario: Consolidating in a way I can undo
Problem: I'm not sure the two records are really the same paper.
Action:  zotero-cli item merge --master "IEEE_KEY1" --duplicates "SPR_KEY2" --trash --execute
Result:  The same merge, but SPR_KEY2 goes to Zotero's trash; `item restore --key "SPR_KEY2" --execute` brings it back (its notes and attachments stay on the master).

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
• Safety Tips: Without --trash this is PERMANENT: the duplicates are deleted for good and there is no undo. With --trash they go to Zotero's trash and can be restored (their notes and attachments stay on the master). Run without --execute first to preview. Any citation-management document referencing a duplicate's key by that key will break.

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
        merge_p.add_argument(
            "--trash",
            action="store_true",
            help="Move the emptied duplicates to Zotero's trash (recoverable) instead of deleting them permanently",
        )

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
            raise UsageError("Provide either (--master and --duplicates) or --from-plan.")

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
                console.print(f"  [bold]{safe_markup(conflict.field_name)}[/bold]:")
                for key, value in conflict.values.items():
                    console.print(f"    {safe_markup(key)}: {escape(repr(value))}")
                choices = [v for v in conflict.values.values() if v]
                field_resolutions[conflict.field_name] = Prompt.ask(
                    f"  Value to keep for '{safe_markup(conflict.field_name)}'",
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
                console.print(f"[red]Error:[/red] {escape(error)}")
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

        trash = getattr(args, "trash", False) is True
        if not args.execute:
            console.print(
                "[yellow]Preview only - nothing was written. "
                + (
                    "The duplicates will go to Zotero's trash and can be restored."
                    if trash
                    else "This merge is PERMANENT and cannot be undone once run with --execute."
                )
                + " Re-run with --execute to apply.[/yellow]"
            )
            return

        if not args.force:
            console.print(
                f"[yellow]About to {safe_markup('move' if trash else 'permanently delete')} "
                f"{len(duplicate_keys)} item(s) {safe_markup('to the trash' if trash else '')} "
                "after moving their notes/attachments to the master."
                + ("" if trash else " This cannot be undone.")
                + "[/yellow]"
            )
            if not Confirm.ask("Proceed?"):
                console.print(ABORTED_NO_WRITES_MSG)
                return

        result = service.merge(
            master_key,
            duplicate_keys,
            field_resolutions=field_resolutions,
            dry_run=False,
            trash=trash,
        )
        for error in result.errors:
            console.print(f"[red]Warning:[/red] {escape(error)}")
        if result.success:
            console.print(
                f"[green]Merged {len(result.merged_keys)} duplicate(s) into "
                f"'{safe_markup(result.master_key)}'.[/green]"
            )
        else:
            console.print("[red]Merge did not complete successfully - see warnings above.[/red]")

    def _handle_merge_from_plan(self, args: argparse.Namespace) -> None:
        from pathlib import Path

        from rich.prompt import Confirm

        from zotero_cli.core.services.merge_plan_io import parse_plan_from_csv, parse_plan_from_json

        path = Path(args.from_plan)
        if not path.exists():
            raise NotFound(f"Plan file '{path}' not found.")

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
                    safe_markup(entry.decision.reason),
                )
        console.print(table)

        if not preview.success:
            console.print(
                "[red]Plan is incomplete - nothing will be written until every group has a "
                "decision:[/red]"
            )
            for error in preview.errors:
                console.print(f"  [red]{escape(error)}[/red]")
            return

        trash = getattr(args, "trash", False) is True
        if not args.execute:
            console.print(
                "[yellow]Preview only - nothing was written. "
                + (
                    "The duplicates will go to Zotero's trash and can be restored."
                    if trash
                    else "This merge is PERMANENT and cannot be undone once run with --execute."
                )
                + " Re-run with --execute to apply.[/yellow]"
            )
            return

        if not args.force:
            groups_with_merges = sum(1 for e in plan.entries if e.decision and e.decision.merge_keys)
            console.print(
                f"[yellow]About to execute {safe_markup(groups_with_merges)} merge(s) from this plan. "
                + ("The duplicates go to the trash." if trash else "This cannot be undone.")
                + "[/yellow]"
            )
            if not Confirm.ask("Proceed?"):
                console.print(ABORTED_NO_WRITES_MSG)
                return

        result = service.execute_plan(plan, dry_run=False, trash=trash)
        for group_result in result.group_results:
            for error in group_result.errors:
                console.print(f"[red]Warning ({safe_markup(group_result.master_key)}):[/red] {escape(error)}")
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
                raise UsageError("--collection or --root required for non-trash listings.")
            # The resolver accepts a key or a name (#381); None means neither
            # exists. It used to fall through and print [] (Issue #377).
            col_id = gateway.get_collection_id_by_name(args.collection)
            if not col_id:
                raise NotFound(f"Collection '{args.collection}' not found.")

            items = list(
                gateway.get_items_in_collection(col_id, top_only=getattr(args, "top_only", False))
            )
            title = f"Items in {args.collection}"

        fields = item_list_presenter.parse_fields(
            getattr(args, "fields", None), wide=getattr(args, "wide", False)
        )
        for name in item_list_presenter.unknown_fields(items, fields):
            # stderr, so a --format json/csv stream on stdout stays parseable.
            Console(stderr=True).print(
                f"[yellow]Warning: no listed item has a field named {escape(repr(name))}.[/yellow]"
            )
        item_list_presenter.render(
            items, fields, getattr(args, "format", "table"), title, console
        )

    def _handle_transfer(self, args: argparse.Namespace) -> None:
        from dataclasses import replace

        from zotero_cli.core.config import get_config

        source_gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, "user", False))

        config = get_config()
        # Create a modified config for the destination (Target is always a group in this command)
        dest_config = replace(config, library_id=args.target_group, library_type="group")
        dest_gateway = GatewayFactory.get_zotero_gateway(config=dest_config, force_user=False)

        service = GatewayFactory.get_transfer_service()

        trash = getattr(args, "trash", False) is True
        if trash and not args.delete_source:
            raise UsageError("--trash applies to the source item, so it needs --delete-source.")

        print(f"Transferring item {args.key} to group {args.target_group}...")
        result = service.transfer_item(
            args.key,
            source_gateway,
            dest_gateway,
            delete_source=args.delete_source,
            trash_source=trash,
        )

        if result.new_key is None:
            print(f"Transfer failed: {'; '.join(result.failures)}", file=sys.stderr)
            sys.exit(1)
        print(
            f"Copied to the destination as {result.new_key} "
            f"({result.copied_children} note(s)/attachment(s))."
        )
        if result.failures:
            print("Not copied:", file=sys.stderr)
            for failure in result.failures:
                print(f"  - {failure}", file=sys.stderr)
            if args.delete_source:
                print(
                    f"The source item {args.key} was NOT {'trashed' if trash else 'deleted'}, so nothing is lost. "
                    "Copy the missing parts by hand, then remove it.",
                    file=sys.stderr,
                )
            sys.exit(1)
        if result.source_deleted:
            if trash:
                print(f"Moved the source item {args.key} to the trash (`item restore` undoes it).")
            else:
                print(f"Deleted the source item {args.key}.")

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
            raise UsageError("Specify what to purge using --files, --notes, or --tags.")

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
        import json

        from zotero_cli.core.services.enrichment_service import parse_fields

        if not (args.key or args.collection or args.all):
            print("Error: Specify --key, --collection, or --all.", file=sys.stderr)
            sys.exit(2)
        try:
            fields = parse_fields(getattr(args, "fields", None))
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)
        execute = bool(getattr(args, "execute", False))
        if execute and getattr(args, "offline", False):
            print("Error: --offline is read-only; drop --execute to preview.", file=sys.stderr)
            sys.exit(2)

        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_enrichment_service(force_user=force_user)
        options = {
            "fields": fields,
            "overwrite": bool(getattr(args, "overwrite", False)),
            "by_title": bool(getattr(args, "by_title", False)),
            "execute": execute,
        }
        as_json = getattr(args, "format", "table") == "json"
        progress = Console(stderr=True)

        if args.key:
            single = service.hydrate_item(args.key, **options)
            if single is None:
                print(f"Error: Item '{args.key}' not found.", file=sys.stderr)
                sys.exit(1)
            results = [single]
        elif args.collection:
            if not as_json:
                progress.print(f"Hydrating collection '{safe_markup(args.collection)}'...")
            results = service.hydrate_collection(args.collection, **options)
        else:
            if not as_json:
                progress.print("Hydrating the whole library...")
            results = service.hydrate_all(**options)

        if as_json:
            print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
            return

        with_changes = [r for r in results if r.changes]
        if with_changes:
            title = "Hydration Report" + ("" if execute else " (PREVIEW)")
            table = Table(title=title)
            table.add_column("Key", style="cyan")
            table.add_column("Title", overflow="fold")
            table.add_column("Status")
            table.add_column("Changes", overflow="fold")
            for r in with_changes:
                lines = []
                for name, change in r.changes.items():
                    new = change["new"]
                    shown = f"{len(new)} author(s)" if name == "creators" else str(new)
                    if len(shown) > 80:
                        shown = shown[:77] + "..."
                    old = change["old"]
                    prefix = "" if old in (None, "", []) else "replace "
                    lines.append(f"{prefix}{name}: {shown}")
                table.add_row(
                    r.key,
                    safe_markup(r.title),
                    r.status,
                    safe_markup("\n".join(lines)),
                )
            console.print(table)

        counts: dict = {}
        for r in results:
            counts[r.status] = counts.get(r.status, 0) + 1
        summary = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
        console.print(f"\n{len(results)} item(s): {safe_markup(summary or 'nothing to do')}")
        failed = [r for r in results if r.status == "failed"]
        for r in failed:
            console.print(f"[red]{safe_markup(r.key)}[/red]: {safe_markup(r.message or 'failed')}")
        if not execute and with_changes:
            console.print("[yellow]Preview only - re-run with --execute to write these changes.[/yellow]")

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
                    raise NotFound(f"Collection '{args.collection}' not found.")

            if args.file:
                import os

                if not os.path.exists(args.file):
                    raise NotFound(f"File '{args.file}' not found.")
                with open(args.file, "r") as f:
                    keys.extend([line.strip() for line in f if line.strip()])

            if not keys:
                raise UsageError("Provide a key, --collection, or --file.")

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
                if args.details:
                    console.print(f"Enqueued discovery job {safe_markup(jid)} for item {safe_markup(k)}")

            console.print(
                f"[bold]Starting resilient PDF discovery for {len(unique_keys)} items...[/bold]"
            )
            import asyncio

            asyncio.run(pdf_finder.process_jobs())
            console.print("[bold green]Discovery workers finished.[/bold green]")

        elif args.pdf_verb == "strip":
            purge_service = GatewayFactory.get_purge_service(force_user=force_user)
            dry_run = not args.execute
            stats = purge_service.purge_item_assets(args.key, dry_run=dry_run)
            count = stats["deleted"] if not dry_run else stats["skipped"]
            if dry_run:
                console.print(
                    f"[yellow]DRY RUN:[/yellow] Would remove {count} attachments from {safe_markup(args.key)}."
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
            raise NotFound(f"File not found: {path}")

        mime_type, _ = mimetypes.guess_type(path)
        mime_type = mime_type or "application/octet-stream"

        print(f"Attaching local file: {path} (MIME: {mime_type})")
        if gateway.upload_attachment(args.key, path, mime_type=mime_type):
            print("Successfully attached file.")
        else:
            print("Failed to attach file.")

    def _handle_delete(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        item = gateway.get_item(args.key)
        if not item:
            print(f"Error: Item {args.key} not found.", file=sys.stderr)
            sys.exit(1)

        # Issue #378: predates the preview-by-default policy, so it still
        # applies immediately without either flag - just warns instead of
        # silently keeping the old behaviour forever.
        execute = bool(getattr(args, "execute", False))
        dry_run = bool(getattr(args, "dry_run", False))
        trash = getattr(args, "trash", False) is True
        if not execute and not dry_run:
            # --trash is recoverable and new: no legacy behaviour to warn about.
            if not trash:
                warn_default_apply("item delete")
            execute = True

        if not execute:
            children = gateway.get_item_children(args.key)
            print(f"Would {'move to the trash' if trash else 'delete'} item {args.key}: {item.title}")
            if children and trash:
                print(f"  {len(children)} attached note(s)/file(s) stay with it.")
            elif children:
                print(f"  {len(children)} attached note(s)/file(s) are NOT deleted with it "
                    "(the Web API doesn't cascade) and would become orphaned:")
                for child in children:
                    ctype = child.get("data", {}).get("itemType", "unknown")
                    ckey = str(child.get("key", ""))
                    print(f"    {ckey}  ({ctype})")
            print("Preview only - nothing was changed. Re-run with --execute to apply it.")
            return

        # Issue #384: delete only the version the user saw (--version) or the
        # current one - never whatever the item became in between.
        version = args.version if args.version is not None else item.version
        if trash:
            if gateway.trash_item(args.key, version):
                print(f"Moved item {args.key} to the trash (undo with `item restore --key {args.key} --execute`).")
                return
            print(
                f"Failed to trash item {args.key} (it may have changed since version {version}).",
                file=sys.stderr,
            )
            sys.exit(1)
        if gateway.delete_item(args.key, version):
            print(f"Deleted item {args.key} successfully.")
        else:
            print(
                f"Failed to delete item {args.key} (it may have changed since version {version}).",
                file=sys.stderr,
            )
            sys.exit(1)

    @staticmethod
    def _is_local(gateway: ZoteroGateway) -> bool:
        from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

        return isinstance(gateway, SqliteZoteroGateway)

    def _handle_trash(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        self._trash_or_restore(gateway, args, restore=False)

    def _handle_restore(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        self._trash_or_restore(gateway, args, restore=True)

    def _trash_or_restore(
        self, gateway: ZoteroGateway, args: argparse.Namespace, *, restore: bool
    ) -> None:
        """One command for both backends (Issue #402): the Web API's `deleted`
        flag online, Desktop's own rows in zotero.sqlite with --offline. Desktop
        syncs either way, so the user never has to care which ran."""
        item = gateway.get_item(args.key)
        if not item:
            raise NotFound(f"Item '{args.key}' not found.")

        local = self._is_local(gateway)
        verb, past, target = (
            ("restore", "Restored from trash", "from the trash")
            if restore
            else ("trash", "Moved to trash", "to the trash")
        )
        where = " in zotero.sqlite" if local else ""

        if not args.execute:
            console.print(
                f"[yellow]Preview only[/yellow] - would {safe_markup(verb)} '[cyan]{safe_markup(item.title)}[/cyan]' "
                f"([magenta]{safe_markup(args.key)}[/magenta]) {safe_markup(target)}{safe_markup(where)}. Re-run with "
                "--execute to apply."
            )
            return

        # Only a direct database write needs the extra warning and prompt; a
        # trash through the API is recoverable and versioned.
        if local and not args.force:
            from rich.prompt import Confirm

            console.print(
                "[yellow]This writes directly to your local zotero.sqlite, the same file "
                "Zotero Desktop reads. Close Desktop first to avoid a database lock.[/yellow]"
            )
            question = f"{verb.capitalize()} '{safe_markup(item.title)}' ({safe_markup(args.key)})"
            if not Confirm.ask(f"{question} {safe_markup(target)}?"):
                console.print(ABORTED_NO_WRITES_MSG)
                return

        done = (
            gateway.restore_item(args.key, item.version)
            if restore
            else gateway.trash_item(args.key, item.version)
        )
        if done:
            console.print(f"[bold green]{safe_markup(past)}:[/bold green] {safe_markup(args.key)}")
        else:
            print(f"Failed to {verb} item {args.key} (it may have changed since it was read).", file=sys.stderr)
            sys.exit(1)

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
            raise UsageError("No updates provided. Use --doi, --title, --abstract, or --json.")

        version = args.version
        if version is None:
            item = gateway.get_item(args.key)
            if not item:
                raise NotFound(f"Item {args.key} not found.")
            version = item.version

        if gateway.update_item(args.key, version, payload):
            print(f"Updated item {args.key} successfully.")
        else:
            print(f"Failed to update item {args.key}.")

    def _handle_move(self, args: argparse.Namespace) -> None:
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_collection_service(force_user=force_user)
        if service.move_item(args.source, args.target, args.key):
            source_display = args.source or "auto"
            target_display = args.target
            if target_display.lower() in ["/", "root", "unfiled"]:
                target_display = "Root (Unfiled Items)"
            if source_display.lower() in ["/", "root", "unfiled"]:
                source_display = "Root (Unfiled Items)"

            print(f"Moved item {args.key} from {source_display} to {target_display}.")
        else:
            print("Failed to move item.")

    def _handle_export(self, args: argparse.Namespace) -> None:
        from pathlib import Path

        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        item = gateway.get_item(args.key)
        if not item:
            raise NotFound(f"Item '{args.key}' not found.")

        if args.export_format == "md":
            attach_service = GatewayFactory.get_attachment_service(force_user=force_user)
            output_dir = Path(args.output) if args.output else Path("./export_md")
            output_dir.mkdir(parents=True, exist_ok=True)

            console.print(f"Exporting full-text for: [cyan]{escape(item.title or '')}[/cyan]...")
            stats = attach_service.bulk_export_markdown([item], output_dir)

            if stats["success"] > 0:
                console.print(f"[bold green]Success![/bold green] Markdown saved to {safe_markup(output_dir)}")
            elif stats["skipped"] > 0:
                console.print("[yellow]Skipped:[/yellow] Item has no PDF attachment.")
            else:
                console.print("[bold red]Failed:[/bold red] Could not extract text from PDF.")
                sys.exit(1)
        else:
            # BibTeX / RIS
            if not args.output:
                raise UsageError("--output required for metadata export.")

            export_service = GatewayFactory.get_export_service(force_user=force_user)
            console.print(
                f"Exporting item [cyan]{safe_markup(args.key)}[/cyan] to [green]{safe_markup(args.output)}[/green] ({safe_markup(args.export_format)})..."
            )
            if export_service.export_items([item], args.output, args.export_format):
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
            raise ZoteroCliError(f"Could not fetch template for type '{args.type}'.")

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
        console.print(f"Creating new [cyan]{safe_markup(args.type)}[/cyan]: [bold]{escape(args.title)}[/bold]...")
        new_key = gateway.create_generic_item(template)

        if new_key:
            console.print(
                f"[bold green]Success![/bold green] Item created with key: [magenta]{safe_markup(new_key)}[/magenta]"
            )
        else:
            console.print("[bold red]Error:[/bold red] Failed to create item.")

