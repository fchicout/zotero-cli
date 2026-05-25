import argparse

from rich.console import Console

console = Console()


class SDBCommand:
    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        sdb_sub = parser.add_subparsers(dest="sdb_verb", required=True)

        # inspect
        inspect_p = sdb_sub.add_parser("inspect", help="Show all SDB notes for an item")
        inspect_p.add_argument("key", help="Item Key")

        # edit
        edit_p = sdb_sub.add_parser("edit", help="Edit an existing SDB entry")
        edit_p.add_argument("key", help="Item Key")
        edit_p.add_argument("--persona", required=True)
        edit_p.add_argument("--phase", required=True)
        edit_p.add_argument("--set-decision", choices=["accepted", "rejected", "unknown"])
        edit_p.add_argument("--execute", action="store_true", help="Apply changes")

        # upgrade
        upgrade_p = sdb_sub.add_parser("upgrade", help="Upgrade SDB entries to latest version")
        upgrade_p.add_argument("--collection", required=True)
        upgrade_p.add_argument("--execute", action="store_true")

        # reset
        reset_p = sdb_sub.add_parser(
            "reset",
            help="Reset screening/audit metadata for a collection",
            description="Permanently deletes screening decisions and audit metadata for items in a specific collection and review phase.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        reset_p.add_argument("--name", required=True, help="Collection name or key")
        reset_p.add_argument("--phase", required=True, help="Target phase to reset")
        reset_p.add_argument("--persona", help="Reviewer persona to reset (Optional)")
        reset_p.add_argument("--force", action="store_true", help="Skip confirmation")

        # export
        export_p = sdb_sub.add_parser(
            "export",
            help="Recover/Sync local CSV from Zotero screening notes",
            description="Exports the current state of screening decisions from Zotero into a local CSV file, effectively creating an offline 'mirror' of your research audit trail.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        export_p.add_argument("--collection", required=True, help="Collection name or key")
        export_p.add_argument("--output", required=True, help="Path to output CSV")

    @staticmethod
    def execute(gateway, args: argparse.Namespace):
        from zotero_cli.core.services.sdb.sdb_service import SDBService

        service = SDBService(gateway)

        if args.sdb_verb == "inspect":
            entries = service.inspect_item_sdb(args.key)
            if not entries:
                console.print(f"[yellow]No SDB entries found for {args.key}[/yellow]")
                return
            table = service.build_inspect_table(args.key, entries)
            console.print(table)

        elif args.sdb_verb == "edit":
            changes = {}
            if args.set_decision:
                changes["decision"] = args.set_decision

            success, msg = service.edit_sdb_entry(
                args.key, args.persona, args.phase, changes, dry_run=not args.execute
            )
            color = "green" if success else "red"
            console.print(f"[{color}]{msg}[/{color}]")

        elif args.sdb_verb == "upgrade":
            if not args.execute:
                console.print(
                    "[yellow]Running SDB Upgrade in DRY-RUN mode. Use --execute to apply.[/yellow]"
                )

            stats = service.upgrade_sdb_entries(args.collection, dry_run=not args.execute)
            console.print(
                f"Scanned: {stats['scanned']}, Upgraded: {stats['upgraded']}, Skipped: {stats['skipped']}, Errors: {stats['errors']}"
            )

        elif args.sdb_verb == "export":
            import sys

            from zotero_cli.core.services.sync_service import SyncService

            sync_service = SyncService(gateway)

            def cli_progress(current, total, msg):
                percent = (current / total * 100) if total > 0 else 0
                sys.stdout.write(f"\r[{percent:5.1f}%] {msg:<60}")
                sys.stdout.flush()

            print(f"Syncing local CSV from '{args.collection}' notes...")
            success = sync_service.recover_state_from_notes(args.collection, args.output, cli_progress)
            print("")
            if not success:
                sys.exit(1)

        elif args.sdb_verb == "reset":
            from rich.prompt import Confirm

            from zotero_cli.core.services.purge_service import PurgeService

            # 1. Resolve Items
            col_id = gateway.get_collection_id_by_name(args.name)
            if not col_id:
                col_id = args.name
            items = list(gateway.get_items_in_collection(col_id))
            if not items:
                console.print(f"[yellow]No items found in '{args.name}'.[/yellow]")
                return

            keys = [i.key for i in items]

            # 2. Confirmation
            if not args.force:
                if not Confirm.ask(
                    f"Are you sure you want to reset {args.phase} metadata for {len(keys)} items in '{args.name}'?"
                ):
                    return

            # 3. Purge
            purge_service = PurgeService(gateway)
            dry_run = not args.force

            note_stats = purge_service.purge_notes(
                keys, sdb_only=True, phase=args.phase, persona=args.persona, dry_run=dry_run
            )
            tag_name = f"rsl:phase:{args.phase}"
            tag_stats = purge_service.purge_tags(keys, tag_name=tag_name, dry_run=dry_run)

            console.print(f"\n[bold]Reset results for '{args.name}' (Phase: {args.phase}):[/bold]")
            console.print(f" - Notes purged: {note_stats['deleted']}")
            console.print(f" - Tags purged:  {tag_stats['deleted']}")
            if dry_run:
                console.print("[yellow]DRY RUN COMPLETE. No changes applied.[/yellow]")
            else:
                console.print("[bold green]Reset complete.[/bold green]")
