import argparse
import asyncio
import sys

from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
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
        sub.add_parser(
            "list",
            help="List all collections",
            description="Displays a structured list of all collections (folders) available in the active Zotero library, including their unique keys and hierarchical relationships.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Finding a collection key for a new task
Problem: I need to run a RAG ingestion on a specific folder, but I only know its name is "Deep Learning."
Action:  zotero-cli collection list
Result:  The table displays all collections. I locate "Deep Learning" and find its key is G5H6J7K8.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to run in offline mode without a pre-existing local database synchronization.
• Safety Tips: If your library has a very deep hierarchy, the table will display parent keys. Use these keys to distinguish between collections with the same name.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_list.md
""",
        )

        # Create
        create_p = sub.add_parser(
            "create",
            help="Create a new collection",
            description="Creates a new collection (folder) in your library, either at the root level or nested within an existing collection.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Organizing papers for a specific study
Problem: I need a new folder named "Reinforcement Learning" under my existing "Artificial Intelligence" (Key: AI_CORE) folder.
Action:  zotero-cli collection create --name "Reinforcement Learning" --parent "AI_CORE"
Result:  A new sub-folder is created, and the CLI returns its unique key (e.g., RL_ROOT).

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to create a collection with a name that contains special characters that might conflict with shell environment variables. Use double quotes around the name.
• Safety Tips: Always verify that the parent key is correct by running collection list first. Creating deep nested structures can lead to complex workflows.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_create.md
""",
        )
        create_p.add_argument("--name", required=True, help="Collection name")
        create_p.add_argument("--parent", help="Parent collection name or key")

        # Delete
        delete_p = sub.add_parser(
            "delete",
            help="Delete a collection",
            description="Removes a specified collection from your library. This operation is irreversible and can include recursive deletion of sub-folders and items.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Cleaning up an old project
Problem: I have a folder "Obsolete_SLR_2023" (Key: OLD_123) that I no longer need.
Action:  zotero-cli collection delete --key "OLD_123" --recursive
Result:  The folder and all its contents are permanently removed from the library.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to delete a folder without the --recursive flag when it still contains items. This will result in an API error.
• Safety Tips: ALWAYS run collection list before deletion to verify the key and ensure you are not deleting a critical parent folder. Deletion is irreversible.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_delete.md
""",
        )
        delete_p.add_argument("--key", required=True, help="Collection name or key")
        delete_p.add_argument(
            "--version", type=int, help="Collection version (optional if recursive)"
        )
        delete_p.add_argument(
            "--recursive", action="store_true", help="Delete all items and sub-collections"
        )

        # Rename
        rename_p = sub.add_parser(
            "rename",
            help="Rename a collection",
            description="Changes the display name of an existing collection in your library without affecting its contents or hierarchical position.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Evolving a research focus
Problem: My collection "Machine Learning Basic" (Key: ML_01) needs a more professional name for a publication.
Action:  zotero-cli collection rename --key "ML_01" --name "Fundamentals of Reinforcement Learning"
Result:  The folder is renamed, but all internal items and its unique key (ML_01) remain unchanged.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to rename a collection using an outdated version number (if --version is provided). This will result in a synchronization error.
• Safety Tips: If you have multiple folders with the same name across different parents, always use the Collection Key for a guaranteed deterministic rename.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_rename.md
""",
        )
        rename_p.add_argument("--key", required=True, help="Current name or key")
        rename_p.add_argument("--name", required=True, help="New name")
        rename_p.add_argument("--version", type=int, help="Collection version")

        # Clean
        clean_p = sub.add_parser(
            "clean",
            help="Empty all items from a collection (Does not delete collection)",
            description="Empties a collection by removing all associated items from it. Note that this command does not delete the items from the library, only their association with this specific collection.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Resetting a screening results folder
Problem: My "Screened Results" folder (Key: SCR_456) has outdated data from a previous attempt and I want to start fresh.
Action:  zotero-cli collection clean --collection "SCR_456"
Result:  The folder is now empty and ready for a new set of items.

Cognitive Safeguards
--------------------
• Common Failure Modes: Confusion between clean and delete. clean keeps the folder structure intact, while delete removes the folder itself.
• Safety Tips: Use collection list to verify the collection key before cleaning. If your items are not linked to any other collection, they will become unfiled in your main library.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_clean.md
""",
        )
        clean_p.add_argument("--collection", required=True, help="Collection name or key")
        clean_p.add_argument("--verbose", action="store_true")

        # Duplicates
        dupe_p = sub.add_parser(
            "duplicates",
            help="Find duplicate items across collections",
            description="Identifies duplicate items that exist across multiple specified collections, facilitating library cleanup and systematic review consistency.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Identifying overlaps between search databases
Problem: I've imported search results from IEEE (Key: IEEE_01) and Springer (Key: SPR_01) and want to see which papers are duplicates.
Action:  zotero-cli collection duplicates --collections "IEEE_01,SPR_01"
Result:  The CLI displays a table showing papers that were found in both collections, including their titles and keys.

Cognitive Safeguards
--------------------
• Common Failure Modes: Providing collection names that include commas or special characters without quoting.
• Safety Tips: This command only identifies duplicates; it does not automatically merge or delete them. Use the item delete or slr prune commands to act on the findings.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_duplicates.md
""",
        )
        dupe_p.add_argument(
            "--collections", required=True, help="Comma-separated list of collection names or keys"
        )

        # PDF operations
        pdf_p = sub.add_parser(
            "pdf",
            help="Bulk PDF attachment operations",
            description="Performs bulk operations on PDF attachments across an entire collection, either fetching missing files from online sources or stripping all existing attachments.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_pdf.md
""",
        )
        pdf_sub = pdf_p.add_subparsers(dest="pdf_verb", required=True)

        fetch_p = pdf_sub.add_parser(
            "fetch",
            help="Fetch missing PDFs for all items in a collection",
            description="Scans the specified collection for items without PDF attachments and attempts to retrieve them using DOIs and other metadata through integrated providers (like ArXiv, CrossRef).",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Mass retrieval of papers for reading
Problem: I've imported 200 items into my "Reading List" (Key: READ_123) but they only have metadata and no PDFs.
Action:  zotero-cli collection pdf fetch --collection "READ_123"
Result:  The CLI attempts to find and download PDFs for all 200 items automatically.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting fetch without a working internet connection or with items that lack a DOI/ArXiv ID.
• Safety Tips: Always ensure you have sufficient disk space before running fetch on large collections.
""",
        )
        fetch_p.add_argument("--collection", required=True, help="Collection name or key")

        strip_p = pdf_sub.add_parser(
            "strip",
            help="Remove all PDF attachments from a collection",
            description="Permanently removes all PDF attachments from every item in a collection.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Cognitive Safeguards
--------------------
• Common Failure Modes: strip is irreversible and will permanently delete files from your Zotero storage.
• Safety Tips: Use strip with extreme caution. Always backup your library before mass deletion.
""",
        )
        strip_p.add_argument("--collection", required=True, help="Collection name or key")
        strip_p.add_argument("--execute", action="store_true", help="Actually perform deletions")
        strip_p.add_argument("--verbose", action="store_true")

        # Backup
        backup_p = sub.add_parser(
            "backup",
            help="Backup a collection to .zaf archive",
            description="Creates a self-contained, portable backup archive (.zaf) of a specific collection, including all item metadata and PDF attachments.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Archiving a completed SLR project
Problem: I have finished my SLR (Key: SLR_PROJ_2025) and I want to save a permanent, offline version of the final included items and their PDFs.
Action:  zotero-cli collection backup --name "SLR_PROJ_2025" --output "Final_SLR_Archive.zaf"
Result:  A single portable file is created that contains everything needed to reconstruct the project state later.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to backup to a directory without write permissions or to an external drive with insufficient space.
• Safety Tips: Always perform a backup before using destructive commands like collection clean or collection delete. The .zaf format can be restored using the system restore command.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_backup.md
""",
        )
        backup_p.add_argument("--name", required=True, help="Collection name or key")
        backup_p.add_argument("--output", required=True, help="Output file path")

        # Export
        export_p = sub.add_parser(
            "export",
            help="Export collection metadata or content",
            description="Exports the metadata and (optionally) content of a collection into various standard formats for use in citation managers, LaTeX documents, or research notes.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Syncing literature with a LaTeX project
Problem: I need to update the .bib file for my paper with the latest items in my "Final Selection" folder (Key: FIN_01).
Action:  zotero-cli collection export --name "FIN_01" --format bibtex --output "references.bib"
Result:  The file references.bib is created/updated with the metadata from that folder.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to export to a restricted directory or choosing a format that doesn't support specific metadata fields.
• Safety Tips: Use the md format to generate a searchable "Digital Library" in Markdown. This enables you to link papers and notes locally.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_export.md
""",
        )
        export_p.add_argument("--name", required=True, help="Collection name or key")
        export_p.add_argument(
            "--format", default="bibtex", choices=["bibtex", "ris", "md"], help="Export format"
        )
        export_p.add_argument("--output", help="Output file path or directory (for md)")

    def execute(self, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        if args.verb == "list":
            self._handle_list(gateway, args)
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
        elif args.verb == "export":
            self._handle_export(args)
        elif args.verb == "purge":
            self._handle_purge(args)

    def _handle_list(self, gateway, args):
        cols = gateway.get_all_collections()
        table = Table(title="Zotero Collections")
        table.add_column("Name")
        table.add_column("Key", style="cyan")
        table.add_column("Items", justify="right")
        for c in cols:
            table.add_row(c["data"]["name"], c["key"], str(c["meta"].get("numItems", 0)))
        console.print(table)

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
            msg = f"Are you sure you want to purge {', '.join(types)} from collection '{args.name}'"
            if args.recursive:
                msg += " and its sub-collections"
            msg += "?"

            if not Confirm.ask(msg):
                console.print("[yellow]Aborted.[/]")
                return

        service = GatewayFactory.get_purge_service(force_user=getattr(args, "user", False))
        stats = service.purge_collection_assets(
            args.name, types=types, recursive=args.recursive, dry_run=False
        )

        console.print(
            f"[green]Purge Complete:[/green] Deleted: {stats['deleted']}, Errors: {stats['errors']}"
        )

    def _handle_clean(self, args):
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_collection_service(force_user=force_user)
        count = service.empty_collection(args.collection, args.verbose)
        print(f"Deleted {count} items from '{args.collection}'.")

    def _handle_pdf(self, args):
        force_user = getattr(args, "user", False)
        if args.pdf_verb == "fetch":
            service = GatewayFactory.get_attachment_service(force_user=force_user)
            pdf_finder = GatewayFactory.get_pdf_finder_service(force_user=force_user)

            job_ids = service.attach_pdfs_to_collection(args.collection)
            if not job_ids:
                console.print(f"[yellow]No items in '{args.collection}' missing PDFs.[/]")
                return

            console.print(f"[green]Enqueued {len(job_ids)} discovery jobs.[/]")
            console.print("[bold]Starting resilient PDF discovery...[/]")

            # Blocking worker for transparent upgrade
            asyncio.run(pdf_finder.process_jobs(count=len(job_ids)))

            console.print(f"[bold green]Done processing collection '{args.collection}'.[/]")
        elif args.pdf_verb == "strip":
            service = GatewayFactory.get_attachment_service(force_user=force_user)
            dry_run = not args.execute
            count = service.remove_attachments_from_collection(args.collection, dry_run=dry_run)
            if dry_run:
                print(
                    f"[yellow]DRY RUN:[/yellow] Would remove {count} attachments from collection '{args.collection}'."
                )
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
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            TextColumn,
            TimeRemainingColumn,
        )

        # Resolve collection ID
        col_id = gateway.get_collection_id_by_name(args.name)
        if not col_id:
            col_id = args.name

        col = gateway.get_collection(col_id)
        if not col:
            console.print(f"[bold red]Error:[/bold red] Collection '{args.name}' not found.")
            return

        total_items = col.get("meta", {}).get("numItems")

        service = BackupService(gateway)
        console.print(f"Starting Backup for Collection '[cyan]{args.name}[/cyan]' ({col_id}) to [green]{args.output}[/green]...")
        
        try:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Backing up items...", total=total_items)
                
                def on_item(item):
                    progress.update(task, advance=1, description=f"Backing up: {item.key}")

                service.backup_collection(col_id, args.output, on_item_processed=on_item)
                progress.update(task, description="Finalizing .zaf container...")

            console.print(f"[bold green]Backup complete:[/bold green] {args.output}")
        except Exception as e:
            console.print(f"[bold red]Backup failed:[/bold red] {e}")

    def _handle_export(self, args):
        if args.format == "md":
            self._handle_export_markdown(args)
        else:
            self._handle_export_metadata(args)

    def _handle_export_metadata(self, args):
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_export_service(force_user=force_user)

        if not args.output:
            console.print("[red]Error: --output required for metadata export.[/red]")
            return

        print(f"Exporting collection '{args.name}' to {args.output} ({args.format})...")
        if service.export_collection(args.name, args.output, args.format):
            print(f"Export complete: {args.output}")
        else:
            print("Export failed.", file=sys.stderr)
            sys.exit(1)

    def _handle_export_markdown(self, args):
        from pathlib import Path

        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            TextColumn,
            TimeRemainingColumn,
        )

        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
        attach_service = GatewayFactory.get_attachment_service(force_user=force_user)

        # 1. Resolve Collection
        col_id = gateway.get_collection_id_by_name(args.name)
        if not col_id:
            col_id = args.name  # Try as raw key

        if not gateway.get_collection(col_id):
            console.print(f"[bold red]Error:[/bold red] Collection '{args.name}' not found.")
            return

        # 2. Get Items
        items = list(gateway.get_items_in_collection(col_id))
        if not items:
            console.print(f"[yellow]No items found in collection '{args.name}'.[/yellow]")
            return

        output_dir = Path(args.output) if args.output else Path("./export_md")
        output_dir.mkdir(parents=True, exist_ok=True)

        console.print(
            f"Exporting [bold]{len(items)}[/bold] items from '[cyan]{args.name}[/cyan]' to [green]{output_dir}[/green]..."
        )

        # 3. Bulk Export with Progress
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Converting PDFs...", total=len(items))

            stats = {"total": len(items), "success": 0, "failed": 0, "skipped": 0}

            for item in items:
                progress.update(task, description=f"Processing: {item.key}")
                result = attach_service._export_item_markdown(item, output_dir)
                if result == "success":
                    stats["success"] += 1
                elif result == "skipped":
                    stats["skipped"] += 1
                else:
                    stats["failed"] += 1
                progress.advance(task)

        # 4. Report
        console.print("\n[bold]Export Summary:[/bold]")
        console.print(f"  - [green]Success:[/green] {stats['success']}")
        console.print(f"  - [yellow]Skipped (No PDF):[/yellow] {stats['skipped']}")
        console.print(f"  - [red]Failed:[/red] {stats['failed']}")
        console.print(f"\nFiles saved to: [bold]{output_dir.absolute()}[/bold]")
