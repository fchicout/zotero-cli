import argparse
from pathlib import Path

from zotero_cli.cli.tui.factory import TUIFactory
from zotero_cli.core.exceptions import ZoteroCliError
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.utils.terminal_safety import safe_markup
from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.infra.opener import OpenerService

console = Console()

_EXPORT_FORMATS = {".json": "json", ".md": "markdown"}


class ExtractionCommand:
    @staticmethod
    def register_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--collection", help="Collection name or key")
        parser.add_argument("--key", help="Item key (for single item extraction)")
        parser.add_argument("--agent", action="store_true", help="Run in Agent-led mode")
        parser.add_argument("--persona", help="Reviewer persona (for Agent-led mode)")
        parser.add_argument(
            "--export",
            help="Write the saved extractions as a matrix to this file instead of extracting "
            "(.json, .md or .csv by extension; --persona picks whose notes)",
        )

    @staticmethod
    def execute(args: argparse.Namespace) -> None:
        force_user = getattr(args, "user", False)
        ext_service = GatewayFactory.get_extraction_service(force_user=force_user)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        # 1. Resolve items
        items = []
        if args.key:
            item = gateway.get_item(args.key)
            if item:
                items = [item]
        elif args.collection:
            col_id = gateway.get_collection_id_by_name(args.collection) or args.collection
            items = list(gateway.get_items_in_collection(col_id))

        if not items:
            raise ZoteroCliError("No items found for extraction.")

        # 2. Export mode: the saved extraction notes of one persona, as a matrix
        if args.export:
            output_format = _EXPORT_FORMATS.get(Path(args.export).suffix.lower(), "csv")
            try:
                path = ext_service.export_matrix(
                    items,
                    output_format=output_format,
                    persona=args.persona or "unknown",
                    output_path=args.export,
                )
            except (FileNotFoundError, ValueError) as e:
                raise ZoteroCliError(f"Cannot export the extraction matrix: {e}") from e
            console.print(
                f"[bold green]Exported extraction matrix to: {safe_markup(path)}[/bold green]"
            )
            return

        # 3. Launch TUI via Factory
        opener = OpenerService()
        tui = TUIFactory.get_extraction_tui(ext_service, opener)
        tui.run_extraction(items, agent=args.agent, persona=args.persona)
