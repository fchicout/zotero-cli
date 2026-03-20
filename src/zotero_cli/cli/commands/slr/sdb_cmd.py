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
                console.print("[yellow]Running SDB Upgrade in DRY-RUN mode. Use --execute to apply.[/yellow]")

            stats = service.upgrade_sdb_entries(args.collection, dry_run=not args.execute)
            console.print(
                f"Scanned: {stats['scanned']}, Upgraded: {stats['upgraded']}, Skipped: {stats['skipped']}, Errors: {stats['errors']}"
            )
