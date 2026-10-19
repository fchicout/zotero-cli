import argparse
import sys

from rich.markup import escape
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.commands import item_annotations
from zotero_cli.cli.commands.item_args import (
    add_add_verb,
    add_annotations_verb,
    add_delete_verb,
    add_export_verb,
    add_hydrate_verb,
    add_list_verb,
    add_merge_verb,
    add_move_verb,
    add_pdf_verb,
    add_purge_verb,
    add_restore_verb,
    add_transfer_verb,
    add_trash_verb,
    add_update_verb,
)
from zotero_cli.cli.commands.item_inspect import InspectCommand, add_inspect_verb
from zotero_cli.cli.flags import (
    user_flag,
)
from zotero_cli.cli.presenters import item_list_presenter
from zotero_cli.cli.safety import resolve_trash
from zotero_cli.core.exceptions import NotFound, UsageError, ZoteroCliError
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.utils.terminal_safety import safe_markup, strip_controls
from zotero_cli.infra.factory import GatewayFactory

console = Console()

ABORTED_NO_WRITES_MSG = "[yellow]Aborted - no writes were made.[/yellow]"


@CommandRegistry.register
class ItemCommand(BaseCommand):
    name = "item"
    help = "Paper/Item operations (move, inspect, delete, etc.)"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        sub = parser.add_subparsers(dest="verb", required=True)
        add_inspect_verb(sub)
        add_move_verb(sub)
        add_list_verb(sub)
        add_update_verb(sub)
        add_pdf_verb(sub)
        add_hydrate_verb(sub)
        add_purge_verb(sub)
        add_delete_verb(sub)
        add_trash_verb(sub)
        add_annotations_verb(sub)
        add_restore_verb(sub)
        add_transfer_verb(sub)
        add_export_verb(sub)
        add_add_verb(sub)
        add_merge_verb(sub)

    def execute(self, args: argparse.Namespace) -> None:
        force_user = user_flag(args)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        if args.verb == "inspect":
            InspectCommand().execute(args)
        elif args.verb == "annotations":
            item_annotations.run(gateway, args)
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

        force_user = user_flag(args)
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

        trash = resolve_trash(args)
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

        force_user = user_flag(args)
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

        trash = resolve_trash(args)
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
            groups_with_merges = sum(
                1 for e in plan.entries if e.decision and e.decision.merge_keys
            )
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
                console.print(
                    f"[red]Warning ({safe_markup(group_result.master_key)}):[/red] {escape(error)}"
                )
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
        item_list_presenter.render(items, fields, getattr(args, "format", "table"), title, console)

    def _handle_transfer(self, args: argparse.Namespace) -> None:
        from dataclasses import replace

        from zotero_cli.core.config import get_config

        source_gateway = GatewayFactory.get_zotero_gateway(force_user=user_flag(args))

        config = get_config()
        # Create a modified config for the destination (Target is always a group in this command)
        dest_config = replace(config, library_id=args.target_group, library_type="group")
        dest_gateway = GatewayFactory.get_zotero_gateway(config=dest_config, force_user=False)

        service = GatewayFactory.get_transfer_service()

        trash = resolve_trash(args)
        chose_trash_or_permanent = (
            getattr(args, "trash", False) is True or getattr(args, "permanent", False) is True
        )
        if chose_trash_or_permanent and not args.delete_source:
            raise UsageError(
                "--trash and --permanent apply to the source item, so they need --delete-source."
            )

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

        service = GatewayFactory.get_purge_service(force_user=user_flag(args))
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

        force_user = user_flag(args)
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
            console.print(
                "[yellow]Preview only - re-run with --execute to write these changes.[/yellow]"
            )

    def _handle_pdf_ops(self, args: argparse.Namespace) -> None:
        force_user = user_flag(args)
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
                    console.print(
                        f"Enqueued discovery job {safe_markup(jid)} for item {safe_markup(k)}"
                    )

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

        # Previews unless --execute (4.0, Issue #462); --dry-run is the explicit spelling.
        execute = bool(getattr(args, "execute", False))
        trash = resolve_trash(args)

        if not execute:
            children = gateway.get_item_children(args.key)
            print(
                f"Would {'move to the trash' if trash else 'delete'} item {args.key}: {item.title}"
            )
            if children and trash:
                print(f"  {len(children)} attached note(s)/file(s) stay with it.")
            elif children:
                print(
                    f"  {len(children)} attached note(s)/file(s) are NOT deleted with it "
                    "(the Web API doesn't cascade) and would become orphaned:"
                )
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
                print(
                    f"Moved item {args.key} to the trash (undo with `item restore --key {args.key} --execute`)."
                )
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
            print(
                f"Failed to {verb} item {args.key} (it may have changed since it was read).",
                file=sys.stderr,
            )
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
        force_user = user_flag(args)
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

        force_user = user_flag(args)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        item = gateway.get_item(args.key)
        if not item:
            raise NotFound(f"Item '{args.key}' not found.")

        include_annotations = bool(getattr(args, "annotations", False))
        if include_annotations and args.export_format != "md":
            raise UsageError("--annotations only applies to --as md.")
        if args.export_format == "md":
            attach_service = GatewayFactory.get_attachment_service(force_user=force_user)
            output_dir = Path(args.output) if args.output else Path("./export_md")
            output_dir.mkdir(parents=True, exist_ok=True)

            console.print(f"Exporting full-text for: [cyan]{escape(item.title or '')}[/cyan]...")
            stats = attach_service.bulk_export_markdown(
                [item], output_dir, include_annotations=include_annotations
            )

            if stats["success"] > 0:
                console.print(
                    f"[bold green]Success![/bold green] Markdown saved to {safe_markup(output_dir)}"
                )
            elif stats["skipped"] > 0:
                console.print("[yellow]Skipped:[/yellow] Item has no PDF attachment.")
            else:
                console.print("[bold red]Failed:[/bold red] Could not extract text from PDF.")
                sys.exit(1)
        elif args.export_format == "bibliography" and not args.output:
            export_service = GatewayFactory.get_export_service(force_user=force_user)
            print(
                strip_controls(
                    export_service.serialize_bibliography([item], args.style, args.render)
                )
            )
        else:
            # BibTeX / RIS / bibliography
            if not args.output:
                raise UsageError("--output required for metadata export.")

            export_service = GatewayFactory.get_export_service(force_user=force_user)
            console.print(
                f"Exporting item [cyan]{safe_markup(args.key)}[/cyan] to [green]{safe_markup(args.output)}[/green] ({safe_markup(args.export_format)})..."
            )
            if args.export_format == "bibliography":
                done = export_service.export_bibliography(
                    [item], args.output, args.style, args.render
                )
            else:
                done = export_service.export_items([item], args.output, args.export_format)
            if done:
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
        console.print(
            f"Creating new [cyan]{safe_markup(args.type)}[/cyan]: [bold]{escape(args.title)}[/bold]..."
        )
        new_key = gateway.create_generic_item(template)

        if new_key:
            console.print(
                f"[bold green]Success![/bold green] Item created with key: [magenta]{safe_markup(new_key)}[/magenta]"
            )
        else:
            console.print("[bold red]Error:[/bold red] Failed to create item.")
