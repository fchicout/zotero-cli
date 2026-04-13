import argparse
import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.infra.factory import GatewayFactory

console = Console()


class InspectCommand(BaseCommand):
    name = "inspect"
    help = "Inspect item details"

    def register_args(self, parser: argparse.ArgumentParser):
        parser.description = "Provides a comprehensive view of all metadata, attachments, and child notes associated with a specific Zotero item."
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Verifying metadata after an import
Problem: I've imported a paper and want to ensure the DOI was correctly captured and check for any existing notes.
Action:  zotero-cli item inspect "ABCD1234"
Result:  The CLI displays a detailed view of the item, including its DOI, abstract, and list of child PDF attachments.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to inspect an item key that does not exist or for which you lack read permissions.
• Safety Tips: Use item list or search to find the correct key if you are unsure. For very large notes, the --full-notes flag may result in a lot of terminal scroll.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_inspect.md
"""
        parser.add_argument("key", help="Zotero Item Key")
        parser.add_argument("--raw", action="store_true", help="Show raw JSON")
        parser.add_argument(
            "--full-notes", action="store_true", help="Show full content of child notes"
        )

    def execute(self, args: argparse.Namespace):
        import json

        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, "user", False))

        item = gateway.get_item(args.key)
        if not item:
            console.print(f"[bold red]Item '{args.key}' not found.[/bold red]")
            return

        if args.raw:
            print(json.dumps(item.raw_data, indent=2))
            return

        console.print(
            Panel(
                f"[bold]Title:[/bold] {item.title}\n"
                f"[bold]Type:[/bold] {item.item_type}\n"
                f"[bold]Date:[/bold] {item.date}\n"
                f"[bold]Authors:[/bold] {', '.join(item.authors)}\n"
                f"[bold]DOI:[/bold] {item.doi}\n"
                f"[bold]URL:[/bold] {item.url}\n\n"
                f"[bold]Abstract:[/bold]\n{item.abstract}",
                title=f"Item: {args.key}",
            )
        )

        # Children (Notes/Attachments)
        children = gateway.get_item_children(args.key)
        if children:
            console.print(f"\n[bold]Children ({len(children)}):[/bold]")
            for child in children:
                ctype = child.get("data", {}).get("itemType", "unknown")
                ckey = child.get("key")
                if ctype == "note":
                    note_full = child.get("data", {}).get("note", "")
                    if args.full_notes:
                        console.print(f"  - [cyan]Note[/cyan] ({ckey}):")
                        console.print(Panel(note_full, border_style="cyan"))
                    else:
                        note_snippet = note_full[:100].replace("\n", " ")
                        console.print(f"  - [cyan]Note[/cyan] ({ckey}): {note_snippet}...")
                else:
                    filename = child.get("data", {}).get("filename", "N/A")
                    console.print(f"  - [green]Attachment[/green] ({ckey}): {filename}")


@CommandRegistry.register
class ItemCommand(BaseCommand):
    name = "item"
    help = "Paper/Item operations (move, inspect, delete, etc.)"

    def register_args(self, parser: argparse.ArgumentParser):
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
            description="Displays a table of research items within a collection, optionally filtering them based on screening decisions, exclusion criteria, or reviewer persona.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Verifying the final selection for a review
Problem: I want to see a list of all 25 items that were accepted in my "Final Selection" folder (Key: FIN_01).
Action:  zotero-cli item list --collection "FIN_01" --included
Result:  The table displays only the 25 accepted items, showing their titles and unique keys.

Cognitive Safeguards
--------------------
• Common Failure Modes: Confusion between the --collection name and key. For deterministic results, always prefer using the unique Key.
• Safety Tips: Use the --top-only flag if you want to exclude child attachments and notes from the list for a cleaner view.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_list.md
""",
        )
        list_p.add_argument("--collection", help="Collection name or key")
        list_p.add_argument("--trash", action="store_true", help="List items in the trash")
        list_p.add_argument("--top-only", action="store_true", help="Only show top-level items")
        list_p.add_argument(
            "--included", action="store_true", help="Filter for items with decision 'accepted'"
        )
        list_p.add_argument(
            "--excluded", action="store_true", help="Filter for items with decision 'rejected'"
        )
        list_p.add_argument("--criteria", help="Filter for items with specific exclusion code")
        list_p.add_argument("--persona", help="Filter by reviewer persona")
        list_p.add_argument("--phase", help="Filter by screening phase")

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
        update_p.add_argument("--key", required=True, help="Item Key")
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
        fetch_p.add_argument("--key", help="Item Key")
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
        strip_p.add_argument("--key", required=True, help="Item Key")
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
        attach_p.add_argument("--key", required=True, help="Item Key")
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
        hydrate_p.add_argument("--key", help="Item Key")
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
        purge_p.add_argument("--key", required=True, help="Item Key")
        purge_p.add_argument("--files", action="store_true", help="Purge attachments/files")
        purge_p.add_argument("--notes", action="store_true", help="Purge notes")
        purge_p.add_argument("--tags", action="store_true", help="Purge tags")
        purge_p.add_argument("--force", action="store_true", help="Skip confirmation")

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
        export_p = sub.add_parser("export", help="Export item metadata or content")
        export_p.add_argument("--key", required=True, help="Item Key")
        export_p.add_argument(
            "--format", default="bibtex", choices=["bibtex", "ris", "md"], help="Export format"
        )
        export_p.add_argument("--output", help="Output file path or directory (for md)")

        # Add
        add_p = sub.add_parser("add", help="Manually add a new item to a collection")
        add_p.add_argument("--collection", required=True, help="Collection name or key")
        add_p.add_argument("--title", required=True, help="Item Title")
        add_p.add_argument("--type", default="journalArticle", help="Item Type (Default: journalArticle)")
        add_p.add_argument("--authors", help="Comma-separated authors (e.g. 'John Doe, Jane Smith')")
        add_p.add_argument("--date", help="Publication Date")
        add_p.add_argument("--abstract", help="Abstract/Note")

    def execute(self, args: argparse.Namespace):
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

    def _handle_list(self, gateway, args):
        from zotero_cli.core.services.sdb.sdb_service import SDBService

        is_sdb_filter = any(
            [
                getattr(args, "included", False),
                getattr(args, "excluded", False),
                getattr(args, "criteria", None),
                getattr(args, "persona", None),
                getattr(args, "phase", None),
            ]
        )

        if getattr(args, "trash", False):
            items = list(gateway.get_trash_items())
            title = "Trash Items"
        else:
            if not getattr(args, "collection", None):
                console.print("[red]Error: --collection required for non-trash listings.[/red]")
                return
            col_id = gateway.get_collection_id_by_name(args.collection)
            if not col_id:
                col_id = args.collection  # Try Key

            items = list(
                gateway.get_items_in_collection(col_id, top_only=getattr(args, "top_only", False))
            )
            title = f"Items in {args.collection}"

        if is_sdb_filter:
            sdb_service = SDBService(gateway)
            filtered_items = []
            sdb_data = {}

            incl = getattr(args, "included", False)
            excl = getattr(args, "excluded", False)
            crit = getattr(args, "criteria", None)
            pers = getattr(args, "persona", None)
            phas = getattr(args, "phase", None)

            for item in items:
                # 1. Fast Filter (Tags)
                if incl and "rsl:include" not in item.tags:
                    continue
                if excl and not any(t.startswith("rsl:exclude:") for t in item.tags):
                    continue
                if crit and f"rsl:exclude:{crit}" not in item.tags:
                    continue

                # 2. Deep Filter (Notes)
                entries = sdb_service.inspect_item_sdb(item.key)
                matched_entry = None
                for entry in entries:
                    match = True
                    if incl and entry.get("decision") != "accepted":
                        match = False
                    if excl and entry.get("decision") != "rejected":
                        match = False
                    if crit:
                        codes = entry.get("reason_code", [])
                        if crit not in codes:
                            match = False
                    if pers and entry.get("persona") != pers:
                        match = False
                    if phas and entry.get("phase") != phas:
                        match = False

                    if match:
                        matched_entry = entry
                        break

                if matched_entry:
                    filtered_items.append(item)
                    sdb_data[item.key] = matched_entry

            if not filtered_items:
                console.print(
                    "[yellow]No items found matching criteria. Ensure SDB metadata is populated.[/yellow]"
                )
                return

            items = filtered_items
            table = Table(title=f"{title} (SDB Filtered)")
            table.add_column("Key", style="cyan")
            table.add_column("Title")
            table.add_column("Decision")
            table.add_column("Criteria")
            table.add_column("Persona")

            for item in items:
                entry = sdb_data[item.key]
                decision = entry.get("decision", "N/A")
                color = "green" if decision == "accepted" else "red"
                criteria = ", ".join(entry.get("reason_code", []))
                table.add_row(
                    item.key,
                    (item.title or "Untitled")[:50],
                    f"[{color}]{decision}[/{color}]",
                    criteria,
                    entry.get("persona", "N/A"),
                )
        else:
            table = Table(title=title)
            table.add_column("Key", style="cyan")
            table.add_column("Title")
            table.add_column("Type")
            for item in items:
                table.add_row(item.key, item.title or "Untitled", item.item_type)

        console.print(table)
        console.print(f"\n[dim]Showing {len(items)} items.[/dim]")

    def _handle_transfer(self, args):
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

    def _handle_purge(self, args):
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

    def _handle_hydrate(self, args):
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

    def _handle_pdf_ops(self, args):
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
            service = GatewayFactory.get_attachment_service(force_user=force_user)
            dry_run = not args.execute
            count = service.remove_attachments_from_item(args.key, dry_run=dry_run)
            if dry_run:
                print(
                    f"[yellow]DRY RUN:[/yellow] Would remove {count} attachments from {args.key}."
                )
            else:
                print(f"Removed {count} attachments from {args.key}.")
        elif args.pdf_verb == "attach":
            gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
            self._handle_pdf_attach(gateway, args)

    def _handle_pdf_attach(self, gateway, args):
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

    def _handle_delete(self, gateway, args):
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

    def _handle_update(self, gateway, args):
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

    def _handle_move(self, args):
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

    def _handle_export(self, args):
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

    def _handle_add(self, gateway, args):
        # 1. Resolve Collection
        col_id = gateway.get_collection_id_by_name(args.collection)
        if not col_id:
            col_id = args.collection  # Try as Key

        # 2. Get Template
        template = gateway.get_item_template(args.type)
        if not template:
            console.print(f"[bold red]Error:[/bold red] Could not fetch template for type '{args.type}'.")
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
            console.print(f"[bold green]Success![/bold green] Item created with key: [magenta]{new_key}[/magenta]")
        else:
            console.print("[bold red]Error:[/bold red] Failed to create item.")
