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
        move_p = sub.add_parser("move", help="Move item between collections")
        move_p.add_argument("--item-id", required=True)
        move_p.add_argument("--source", help="Source collection (optional if unambiguous)")
        move_p.add_argument("--target", required=True)

        # List (Subset of list items)
        list_p = sub.add_parser("list", help="List items in a collection")
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
        update_p = sub.add_parser("update", help="Update item metadata")
        update_p.add_argument("--key", required=True, help="Item Key")
        update_p.add_argument("--doi", help="Update DOI")
        update_p.add_argument("--title", help="Update Title")
        update_p.add_argument("--abstract", help="Update Abstract")
        update_p.add_argument("--json", help="Update using raw JSON string")
        update_p.add_argument(
            "--version", type=int, help="Current version (auto-resolved if omitted)"
        )

        # PDF operations
        pdf_p = sub.add_parser("pdf", help="PDF attachment operations")
        pdf_sub = pdf_p.add_subparsers(dest="pdf_verb", required=True)

        fetch_p = pdf_sub.add_parser("fetch", help="Fetch missing PDF for a specific item")
        fetch_p.add_argument("--key", help="Item Key")
        fetch_p.add_argument("--collection", help="Fetch PDFs for all items in a collection")
        fetch_p.add_argument("--file", help="Fetch PDFs for all items in a key-list file")
        fetch_p.add_argument("--verbose", action="store_true")

        strip_p = pdf_sub.add_parser("strip", help="Remove PDF attachments from a specific item")
        strip_p.add_argument("--key", required=True, help="Item Key")
        strip_p.add_argument("--execute", action="store_true", help="Actually perform deletions")
        strip_p.add_argument("--verbose", action="store_true")

        attach_p = pdf_sub.add_parser("attach", help="Attach a local file to an item")
        attach_p.add_argument("--key", required=True, help="Item Key")
        attach_p.add_argument("--file", required=True, help="Path to local file")

        # Hydrate
        hydrate_p = sub.add_parser(
            "hydrate", help="Enrich metadata from external sources (e.g. ArXiv -> DOI)"
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
        purge_p = sub.add_parser("purge", help="Purge assets (files, notes, tags) from an item")
        purge_p.add_argument("--key", required=True, help="Item Key")
        purge_p.add_argument("--files", action="store_true", help="Purge attachments/files")
        purge_p.add_argument("--notes", action="store_true", help="Purge notes")
        purge_p.add_argument("--tags", action="store_true", help="Purge tags")
        purge_p.add_argument("--force", action="store_true", help="Skip confirmation")

        # Transfer
        transfer_p = sub.add_parser("transfer", help="Transfer item between different libraries")
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
