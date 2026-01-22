import argparse
import sys

from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.commands.list_cmd import ListCommand
from zotero_cli.core.services.backup_service import BackupService
from zotero_cli.core.services.duplicate_service import DuplicateFinder
from zotero_cli.infra.factory import GatewayFactory

console = Console()


@CommandRegistry.register
class CollectionCommand(BaseCommand):
    name = "collection"
    help = "Collection/Folder management"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)

        # List
        sub.add_parser("list", help="List all collections")

        # Create
        create_p = sub.add_parser("create", help="Create a new collection")
        create_p.add_argument("name")
        create_p.add_argument("--parent", help="Parent collection name or key")

        # Delete
        delete_p = sub.add_parser("delete", help="Delete a collection")
        delete_p.add_argument("key", help="Collection name or key")
        delete_p.add_argument(
            "--version", type=int, help="Collection version (optional if recursive)"
        )
        delete_p.add_argument(
            "--recursive", action="store_true", help="Delete all items and sub-collections"
        )

        # Rename
        rename_p = sub.add_parser("rename", help="Rename a collection")
        rename_p.add_argument("key", help="Current name or key")
        rename_p.add_argument("name", help="New name")
        rename_p.add_argument("--version", type=int, help="Collection version")

        # Clean
        clean_p = sub.add_parser(
            "clean", help="Empty all items from a collection (Does not delete collection)"
        )
        clean_p.add_argument("--collection", required=True, help="Collection name or key")
        clean_p.add_argument("--verbose", action="store_true")

        # Duplicates
        dupe_p = sub.add_parser("duplicates", help="Find duplicate items across collections")
        dupe_p.add_argument(
            "--collections", required=True, help="Comma-separated list of collection names or keys"
        )

        # PDF operations
        pdf_p = sub.add_parser("pdf", help="Bulk PDF attachment operations")
        pdf_sub = pdf_p.add_subparsers(dest="pdf_verb", required=True)

        fetch_p = pdf_sub.add_parser(
            "fetch", help="Fetch missing PDFs for all items in a collection"
        )
        fetch_p.add_argument("--collection", required=True, help="Collection name or key")

        strip_p = pdf_sub.add_parser("strip", help="Remove all PDF attachments from a collection")
        strip_p.add_argument("--collection", required=True, help="Collection name or key")
        strip_p.add_argument("--execute", action="store_true", help="Actually perform deletions")
        strip_p.add_argument("--verbose", action="store_true")

        # Backup
        backup_p = sub.add_parser("backup", help="Backup a collection to .zaf archive")
        backup_p.add_argument("--name", required=True, help="Collection name or key")
        backup_p.add_argument("--output", required=True, help="Output file path")

    def execute(self, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        if args.verb == "list":
            args.list_type = "collections"
            ListCommand().execute(args)
        elif args.verb == "create":
            parent_id = None
            if args.parent:
                parent_id = gateway.get_collection_id_by_name(args.parent) or args.parent

            key = gateway.create_collection(args.name, parent_key=parent_id)
            if key:
                print(f"Created collection '{args.name}' (Key: {key})")
            else:
                print("Failed to create collection.")
        elif args.verb == "delete" or args.verb == "rename":
            # Resolve ID from name or key
            col_id = gateway.get_collection_id_by_name(args.key)
            if not col_id:
                col_id = args.key  # Assume it was already a Key

            version = args.version
            if version is None:
                col = gateway.get_collection(col_id)
                if not col:
                    print(f"Collection '{args.key}' not found.")
                    return
                version = col.get("version")

            if args.verb == "delete":
                if args.recursive:
                    print(
                        f"[bold red]WARNING: Performing recursive deletion of collection '{args.key}' ({col_id})...[/bold red]"
                    )

                # Use CollectionService for delete to handle recursive logic
                service = GatewayFactory.get_collection_service(force_user=force_user)
                if service.delete_collection(col_id, version, recursive=args.recursive):
                    print(f"Deleted collection '{args.key}' ({col_id})")
                else:
                    print(f"Failed to delete collection '{args.key}'.")
            else:
                if gateway.rename_collection(col_id, version, args.name):
                    print(f"Renamed collection to '{args.name}'")
                else:
                    print("Failed to rename collection.")
        elif args.verb == "clean":
            self._handle_clean(args)
        elif args.verb == "duplicates":
            self._handle_duplicates(gateway, args)
        elif args.verb == "pdf":
            self._handle_pdf(args)
        elif args.verb == "backup":
            self._handle_backup(gateway, args)

    def _handle_clean(self, args):
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_collection_service(force_user=force_user)
        count = service.empty_collection(args.collection, args.verbose)
        print(f"Deleted {count} items from '{args.collection}'.")

    def _handle_pdf(self, args):
        force_user = getattr(args, "user", False)
        if args.pdf_verb == "fetch":
            service = GatewayFactory.get_attachment_service(force_user=force_user)
            count = service.attach_pdfs_to_collection(args.collection)
            print(f"Fetched {count} PDFs for collection '{args.collection}'.")
        elif args.pdf_verb == "strip":
            service = GatewayFactory.get_attachment_service(force_user=force_user)
            dry_run = not args.execute
            count = service.remove_attachments_from_collection(args.collection, dry_run=dry_run)
            if dry_run:
                print(f"[yellow]DRY RUN:[/yellow] Would remove {count} attachments from collection '{args.collection}'.")
            else:
                print(f"Removed {count} attachments from collection '{args.collection}'.")

    def _handle_duplicates(self, gateway, args):
        service = DuplicateFinder(gateway)
        col_ids = []
        for c in args.collections.split(","):
            c = c.strip()
            # Try to resolve name to ID
            cid = gateway.get_collection_id_by_name(c) or c
            col_ids.append(cid)

        dupes = service.find_duplicates(col_ids)
        if not dupes:
            print("No duplicates found.")
            return
        table = Table(title="Duplicate Items")
        table.add_column("Title")
        table.add_column("DOI")
        table.add_column("Keys")
        for d in dupes:
            table.add_row(d["title"] or "No Title", d["doi"] or "N/A", ", ".join(d["keys"]))
        console.print(table)

    def _handle_backup(self, gateway, args):
        # Resolve collection ID
        col_id = gateway.get_collection_id_by_name(args.name)
        if not col_id:
            col_id = args.name

        service = BackupService(gateway)
        print(f"Starting Backup for Collection '{args.name}' ({col_id})...")
        try:
            service.backup_collection(col_id, args.output)
            print(f"Backup complete: {args.output}")
        except Exception as e:
            print(f"Backup failed: {e}", file=sys.stderr)
