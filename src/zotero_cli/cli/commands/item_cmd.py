import argparse

from rich.console import Console
from rich.panel import Panel

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.commands.list_cmd import ListCommand
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

        # Update
        update_p = sub.add_parser("update", help="Update item metadata")
        update_p.add_argument("key", help="Item Key")
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
        fetch_p.add_argument("key", help="Item Key")
        fetch_p.add_argument("--verbose", action="store_true")

        strip_p = pdf_sub.add_parser("strip", help="Remove PDF attachments from a specific item")
        strip_p.add_argument("key", help="Item Key")
        strip_p.add_argument("--execute", action="store_true", help="Actually perform deletions")
        strip_p.add_argument("--verbose", action="store_true")

        attach_p = pdf_sub.add_parser("attach", help="Attach a local file to an item")
        attach_p.add_argument("key", help="Item Key")
        attach_p.add_argument("path", help="Path to local file")

        # Hydrate
        hydrate_p = sub.add_parser(
            "hydrate", help="Enrich metadata from external sources (e.g. ArXiv -> DOI)"
        )
        hydrate_p.add_argument(
            "key", nargs="?", help="Item Key (optional if --collection or --all)"
        )
        hydrate_p.add_argument("--collection", help="Hydrate all items in a collection")
        hydrate_p.add_argument(
            "--all", action="store_true", help="Scan entire library for hydration"
        )
        hydrate_p.add_argument(
            "--dry-run", action="store_true", help="Show changes without applying"
        )

    def execute(self, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        if args.verb == "inspect":
            InspectCommand().execute(args)
        elif args.verb == "move":
            self._handle_move(args)
        elif args.verb == "list":
            # Adapt args for ListCommand
            args.list_type = "items"
            ListCommand().execute(args)
        elif args.verb == "update":
            self._handle_update(gateway, args)
        elif args.verb == "delete":
            self._handle_delete(gateway, args)
        elif args.verb == "pdf":
            self._handle_pdf_ops(args)
        elif args.verb == "hydrate":
            self._handle_hydrate(args)

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
            service = GatewayFactory.get_attachment_service(force_user=force_user)
            if service.attach_pdf_to_item(args.key):
                print(f"Successfully attached PDF to {args.key}")
            else:
                print(f"Failed to attach PDF to {args.key}")
        elif args.pdf_verb == "strip":
            service = GatewayFactory.get_attachment_service(force_user=force_user)
            dry_run = not args.execute
            count = service.remove_attachments_from_item(args.key, dry_run=dry_run)
            if dry_run:
                print(f"[yellow]DRY RUN:[/yellow] Would remove {count} attachments from {args.key}.")
            else:
                print(f"Removed {count} attachments from {args.key}.")
        elif args.pdf_verb == "attach":
            gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
            self._handle_pdf_attach(gateway, args)

    def _handle_pdf_attach(self, gateway, args):
        import mimetypes
        import os

        path = args.path
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
            print(f"Moved item {args.item_id} from {args.source or 'auto'} to {args.target}.")
        else:
            print("Failed to move item.")
