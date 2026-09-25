import argparse
import sys
from typing import Any, Dict, List, Optional

from rich.markup import escape
from rich.table import Table
from rich.tree import Tree

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.safety import confirm_destructive, preview_notice
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.backup_service import BackupService
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.utils.terminal_safety import safe_markup
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.factory import GatewayFactory

console = Console()

COLLECTION_NAME_OR_KEY_HELP = "Collection name or key"


@CommandRegistry.register
class CollectionCommand(BaseCommand):
    name = "collection"
    help = "Collection/Folder management"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        sub = parser.add_subparsers(dest="verb", required=True)

        # List
        list_p = sub.add_parser(
            "list",
            help="List all collections",
            description="Displays a hierarchical tree of all collections available in the active Zotero library. Each node shows the collection name and its unique ZoteroID in parentheses.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Visualizing the library structure
Problem: I have a complex hierarchy and want to see how my "raw_" folders are organized.
Action:  zotero-cli collection list
Result:  An ASCII tree showing the parent-child relationships.

Scenario: Getting a flat table view
Problem: I need to copy-paste multiple keys into a spreadsheet.
Action:  zotero-cli collection list --table
Result:  A standard flat table with Name, Key, and Item count.
""",
        )
        list_p.add_argument(
            "--table", action="store_true", help="Display results as a flat table instead of a tree"
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
            help="Delete a collection (with --recursive, also its sub-collections and items)",
            description="Deletes a collection. Without --recursive only the collection itself goes; its items stay in your library. With --recursive, its sub-collections and the items filed only inside the tree are permanently deleted too: this previews by default and needs --execute and a confirmation (or --yes).",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Cleaning up an old project
Problem: I have a folder "Obsolete_SLR_2023" (Key: OLD_123) that I no longer need, contents included.
Action:  zotero-cli collection delete --key "OLD_123" --recursive, then add --execute
Result:  The first run lists the sub-collections and items that would be deleted; the second deletes them after you confirm.

Cognitive Safeguards
--------------------
• Items that are also filed in a collection outside the tree are kept (they only leave the deleted collections) unless you pass --include-shared.
• Deletion through the Web API is permanent: it doesn't go through Zotero's trash. Back up first (collection backup).
• A name shared by several collections is refused: pass the key shown in the error.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_delete.md
""",
        )
        delete_p.add_argument("--key", required=True, help=COLLECTION_NAME_OR_KEY_HELP)
        delete_p.add_argument(
            "--version", type=int, help="Collection version (optional if recursive)"
        )
        delete_p.add_argument(
            "--recursive",
            action="store_true",
            help="Also delete the sub-collections and the items filed only inside the tree",
        )
        delete_p.add_argument(
            "--execute",
            action="store_true",
            help="With --recursive: actually delete (default: preview only)",
        )
        delete_p.add_argument(
            "--yes", action="store_true", help="Don't ask for confirmation (for scripts)"
        )
        delete_p.add_argument(
            "--include-shared",
            action="store_true",
            help="With --recursive: also delete items that are filed in other collections",
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
            help="Take every item out of a collection (items stay in the library)",
            description="Empties a collection by removing its items from it. The items are NOT deleted: they stay in your library, and those filed nowhere else appear under Unfiled Items. Previews by default; pass --execute to apply.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Resetting a screening results folder
Problem: My "Screened Results" folder (Key: SCR_456) has outdated data from a previous attempt and I want to start fresh.
Action:  zotero-cli collection clean --collection "SCR_456", then add --execute
Result:  The first run shows how many items would leave the folder; the second empties it. The items remain in your library.

Cognitive Safeguards
--------------------
• clean never deletes items; to delete a folder and its items, use collection delete --recursive.
• Items filed only in this collection end up under Unfiled Items in your library.
• A name shared by several collections is refused: pass the key shown in the error.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_clean.md
""",
        )
        clean_p.add_argument("--collection", required=True, help=COLLECTION_NAME_OR_KEY_HELP)
        clean_p.add_argument(
            "--execute", action="store_true", help="Apply the change (default: preview only)"
        )
        clean_p.add_argument("--verbose", action="store_true", help="List every item affected")

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
        backup_p.add_argument("--name", required=True, help=COLLECTION_NAME_OR_KEY_HELP)
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
        export_p.add_argument("--name", required=True, help=COLLECTION_NAME_OR_KEY_HELP)
        export_p.add_argument(
            "--format", default="bibtex", choices=["bibtex", "ris", "md"], help="Export format"
        )
        export_p.add_argument("--output", help="Output file path or directory (for md)")

        # Purge
        purge_p = sub.add_parser(
            "purge",
            help="Purge assets (files, notes, tags) from every item in a collection",
            description="Permanently removes specific types of child assets (PDFs, notes, or tags) from every item in a collection, without deleting the items or the collection itself.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Clearing stale annotations before a re-screening pass
Problem: My "Full Text Review" folder (Key: FT_01) has old notes and tags from a prior review round that no longer apply.
Action:  zotero-cli collection purge --name "FT_01" --notes --tags
Result:  All notes and tags are removed from every item in the collection, providing a clean slate.

Cognitive Safeguards
--------------------
• Common Failure Modes: Running this without at least one of --files/--notes/--tags - the command aborts with no changes. Forgetting --recursive when sub-collections also need purging.
• Safety Tips: ALWAYS verify the collection with collection list before purging. This command is irreversible.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/collection_purge.md
""",
        )
        purge_p.add_argument("--name", required=True, help=COLLECTION_NAME_OR_KEY_HELP)
        purge_p.add_argument("--files", action="store_true", help="Purge attachments/files")
        purge_p.add_argument("--notes", action="store_true", help="Purge notes")
        purge_p.add_argument("--tags", action="store_true", help="Purge tags")
        purge_p.add_argument(
            "--recursive", action="store_true", help="Apply the purge to sub-collections as well"
        )
        purge_p.add_argument("--force", action="store_true", help="Skip interactive confirmation")

    def execute(self, args: argparse.Namespace) -> None:
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
                    self._handle_recursive_delete(args, col_id, version)
                    return
                service = GatewayFactory.get_collection_service(force_user=force_user)
                if service.delete_collection(col_id, version):
                    print(f"Deleted collection '{args.key}' ({col_id}). Its items stay in your library.")
                else:
                    print(f"Failed to delete collection '{args.key}'.", file=sys.stderr)
                    sys.exit(1)
            else:
                if gateway.rename_collection(col_id, version, args.name):
                    print(f"Renamed collection to '{args.name}'")
                else:
                    print("Failed to rename collection.")
        elif args.verb == "clean":
            self._handle_clean(args)

        elif args.verb == "backup":
            self._handle_backup(gateway, args)
        elif args.verb == "export":
            self._handle_export(args)
        elif args.verb == "purge":
            self._handle_purge(args)

    def _handle_list(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        cols = gateway.get_all_collections()

        if args.table:
            table = Table(title="Zotero Collections")
            table.add_column("Name")
            table.add_column("Key", style="cyan")
            table.add_column("Items", justify="right")
            for c in cols:
                table.add_row(
                    safe_markup(c["data"]["name"]),
                    c["key"],
                    str((c.get("meta") or {}).get("numItems", 0)),
                )
            console.print(table)
            return

        # Tree View [DEFAULT]
        # 1. Build map of key -> children
        by_parent: Dict[Optional[str], List[Dict[str, Any]]] = {}
        by_key = {}
        for c in cols:
            by_key[c["key"]] = c
            parent = c["data"].get("parentCollection")
            if not parent:
                parent = "ROOT"
            if parent not in by_parent:
                by_parent[parent] = []
            by_parent[parent].append(c)

        # 2. Sort by name
        for p in by_parent:
            by_parent[p].sort(key=lambda x: x["data"]["name"])

        # 3. Build Tree
        tree = Tree("Zotero Library (ROOT)")

        def add_nodes(parent_tree: Tree, parent_key: str) -> None:
            children = by_parent.get(parent_key, [])
            for child in children:
                name = child["data"]["name"]
                key = child["key"]
                items = (child.get("meta") or {}).get("numItems", 0)

                # Format node: Name (Key) [Items]
                node_text = f"[bold green]{safe_markup(name)}[/bold green] ([cyan]{key}[/cyan])"
                if items > 0:
                    node_text += f" [dim]({items} items)[/dim]"

                node = parent_tree.add(node_text)
                add_nodes(node, key)

        add_nodes(tree, "ROOT")
        console.print(tree)

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

    def _handle_clean(self, args: argparse.Namespace) -> None:
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_collection_service(force_user=force_user)
        plan = service.plan_clean(args.collection)
        if plan is None:
            print(f"Error: Collection '{args.collection}' not found.", file=sys.stderr)
            sys.exit(1)
        label = f"'{safe_markup(args.collection)}' ({plan.collection_key})"
        if not plan.items:
            console.print(f"{label} is already empty.")
            return
        unfiled = len(plan.becomes_unfiled)
        console.print(
            f"{len(plan.items)} item(s) will be removed from {label}. They stay in your "
            f"library; {unfiled} of them are in no other collection and will appear under "
            "Unfiled Items."
        )
        if getattr(args, "verbose", False):
            for item in plan.items:
                console.print(f"  {item.key}  {safe_markup(item.title or 'Untitled')}")
        if not getattr(args, "execute", False):
            console.print(preview_notice("remove them"))
            return
        removed, failed = service.remove_from_collection(plan)
        console.print(f"Removed {removed} item(s) from {label}.")
        if failed:
            print(f"Failed for {len(failed)} item(s): {', '.join(failed)}", file=sys.stderr)
            sys.exit(1)

    def _handle_recursive_delete(
        self, args: argparse.Namespace, col_id: str, version: Optional[int]
    ) -> None:
        force_user = getattr(args, "user", False)
        service = GatewayFactory.get_collection_service(force_user=force_user)
        plan = service.plan_recursive_delete(col_id, version)
        include_shared = getattr(args, "include_shared", False)
        to_delete = plan.items_to_delete + (plan.shared_items if include_shared else [])

        console.print(
            f"Deleting '{safe_markup(args.key)}' ({col_id}) recursively would permanently delete:"
        )
        console.print(f"  {len(plan.collections)} collection(s):")
        for key, _, name in reversed(plan.collections):
            console.print(f"    {key}  {safe_markup(name)}")
        console.print(f"  {len(to_delete)} item(s) filed only inside this tree")
        if plan.shared_items:
            verb = "WILL ALSO BE DELETED" if include_shared else "will be kept"
            console.print(
                f"  {len(plan.shared_items)} item(s) also filed in other collections {verb}"
                + ("" if include_shared else " (pass --include-shared to delete them too)")
            )
        console.print("Deletion through the Web API is permanent: it bypasses Zotero's trash.")

        if not getattr(args, "execute", False):
            console.print(preview_notice("delete them"))
            return
        if not confirm_destructive("Permanently delete all of the above?", args.yes):
            console.print("Cancelled; nothing was deleted.")
            return
        result = service.execute_recursive_delete(plan, include_shared=include_shared)
        console.print(
            f"Deleted {result.deleted_items} item(s) and {result.deleted_collections} collection(s)."
        )
        if result.failed_items:
            print(
                f"Could not delete {len(result.failed_items)} item(s): "
                f"{', '.join(result.failed_items)}. The collections were left in place.",
                file=sys.stderr,
            )
            sys.exit(1)
        if result.failed_collections:
            print(
                f"Could not delete collection(s): {', '.join(result.failed_collections)}",
                file=sys.stderr,
            )
            sys.exit(1)

    def _handle_backup(self, gateway: ZoteroGateway, args: argparse.Namespace) -> None:
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
            console.print(f"[bold red]Error:[/bold red] Collection '{escape(args.name)}' not found.")
            return

        total_items = col.get("meta", {}).get("numItems")

        service = BackupService(gateway)
        console.print(
            f"Starting Backup for Collection '[cyan]{args.name}[/cyan]' ({col_id}) to [green]{args.output}[/green]..."
        )

        try:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Backing up items...", total=total_items)

                def on_item(item: ZoteroItem) -> None:
                    progress.update(task, advance=1, description=f"Backing up: {item.key}")

                service.backup_collection(col_id, args.output, on_item_processed=on_item)
                progress.update(task, description="Finalizing .zaf container...")

            console.print(f"[bold green]Backup complete:[/bold green] {args.output}")
        except Exception as e:
            console.print(f"[bold red]Backup failed:[/bold red] {escape(str(e))}")

    def _handle_export(self, args: argparse.Namespace) -> None:
        if args.format == "md":
            self._handle_export_markdown(args)
        else:
            self._handle_export_metadata(args)

    def _handle_export_metadata(self, args: argparse.Namespace) -> None:
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

    def _handle_export_markdown(self, args: argparse.Namespace) -> None:
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
            console.print(f"[bold red]Error:[/bold red] Collection '{escape(args.name)}' not found.")
            return

        # 2. Get Items
        items = list(gateway.get_items_in_collection(col_id))
        if not items:
            console.print(f"[yellow]No items found in collection '{escape(args.name)}'.[/yellow]")
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
