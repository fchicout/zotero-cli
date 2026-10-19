"""`item inspect`: the details of one item."""

import argparse

from rich.markup import escape
from rich.panel import Panel

from zotero_cli.cli.base import BaseCommand
from zotero_cli.cli.flags import add_bibliography_flags, add_key_argument, resolve_key, user_flag
from zotero_cli.core.exceptions import NotFound, UsageError
from zotero_cli.core.utils.json_note import decode_json_note
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.utils.terminal_safety import safe_markup, strip_controls
from zotero_cli.infra.factory import GatewayFactory

console = Console()


class InspectCommand(BaseCommand):
    name = "inspect"
    help = "Inspect item details"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.description = "Provides a comprehensive view of all metadata, attachments, and child notes associated with a specific Zotero item."
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """
Examples
--------
Scenario: Verifying metadata after an import
Problem: I've imported a paper and want to ensure the DOI was correctly captured and check for any existing notes.
Action:  zotero-cli item inspect --key "ABCD1234"
Result:  The CLI displays a detailed view of the item, including its DOI, abstract, and list of child PDF attachments.

Notes
-----
• Common Failure Modes: Attempting to inspect an item key that does not exist or for which you lack read permissions.
• Safety Tips: Use item list or search to find the correct key if you are unsure. For very large notes, the --full-notes flag may result in a lot of terminal scroll.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/item_inspect.md
"""
        add_key_argument(
            parser, "Zotero Item Key(s) - comma-separated, e.g. K1,K2,K3", required=False
        )
        parser.add_argument("--file", help="Path to file containing keys (one key per line)")
        parser.add_argument("--raw", action="store_true", help="Show raw JSON")
        parser.add_argument(
            "--as",
            dest="export_format",
            choices=["bibtex", "ris", "bibliography"],
            help="Export in a specific bibliographic format",
        )
        add_bibliography_flags(parser)
        parser.add_argument(
            "--full-notes", action="store_true", help="Show full content of child notes"
        )

    def execute(self, args: argparse.Namespace) -> None:
        import json

        gateway = GatewayFactory.get_zotero_gateway(force_user=user_flag(args))

        resolve_key(args)
        keys = []
        if args.key:
            keys.extend([k.strip() for k in args.key.split(",") if k.strip()])
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                keys.extend([line.strip() for line in f if line.strip()])

        if not keys:
            raise UsageError("You must specify --key or --file.")

        missing: list[str] = []
        for idx, key in enumerate(keys):
            item = gateway.get_item(key)
            if not item:
                missing.append(key)
                continue

            if len(keys) > 1:
                console.print(
                    f"\n[bold yellow]--- Inspecting Item {idx + 1}/{len(keys)}: {safe_markup(key)} ---[/bold yellow]"
                )

            if args.raw:
                print(json.dumps(item.raw_data, indent=2))
                continue

            if args.export_format:
                export_service = GatewayFactory.get_export_service(force_user=user_flag(args))
                # Library fields go to the terminal as-is in these formats:
                # remove control characters (GHSA-3r38-p632-f79q).
                if args.export_format == "bibtex":
                    print(strip_controls(export_service.serialize_bibtex([item])))
                elif args.export_format == "ris":
                    print(strip_controls(export_service.serialize_ris([item])))
                elif args.export_format == "bibliography":
                    print(
                        strip_controls(
                            export_service.serialize_bibliography([item], args.style, args.render)
                        )
                    )
                continue

            # Resolve collections
            col_list = []
            for ckey in item.collections:
                c = gateway.get_collection(ckey)
                name = c.get("data", {}).get("name", ckey) if c else ckey
                col_list.append(f"{name} ({ckey})")
            collections_str = ", ".join(col_list) if col_list else "None"

            abstract_display = (
                safe_markup(item.abstract)
                if item.abstract
                # Plain ASCII, not an emoji glyph: Rich's legacy-Windows
                # renderer writes through the console's codepage (often
                # cp1252), which can't encode arbitrary Unicode and crashed
                # here (found by the #399 release smoke test).
                else "[blink bright_red]<no abstract>[/blink bright_red]"
            )

            console.print(
                Panel(
                    f"[bold]Collections:[/bold] {safe_markup(collections_str)}\n"
                    f"[bold]Title:[/bold] {safe_markup(item.title)}\n"
                    f"[bold]Type:[/bold] {safe_markup(item.item_type)}\n"
                    f"[bold]Date:[/bold] {safe_markup(item.date)}\n"
                    f"[bold]Added:[/bold] {safe_markup(item.date_added)}\n"
                    f"[bold]Modified:[/bold] {safe_markup(item.date_modified)}\n"
                    f"[bold]Authors:[/bold] {safe_markup(', '.join(item.authors))}\n"
                    f"[bold]DOI:[/bold] {safe_markup(item.doi)}\n"
                    f"[bold]URL:[/bold] {safe_markup(item.url)}\n\n"
                    f"[bold]Abstract:[/bold]\n{abstract_display}",
                    title=f"Item: {safe_markup(key)}",
                )
            )

            # Children (Notes/Attachments)
            children = gateway.get_item_children(key)
            if children:
                console.print(f"\n[bold]Children ({len(children)}):[/bold]")
                for child in children:
                    ctype = child.get("data", {}).get("itemType", "unknown")
                    ckey = str(child.get("key", ""))
                    cdata = child.get("data", {})
                    if ctype == "note":
                        note_full = cdata.get("note", "")
                        date_added = cdata.get("dateAdded", "N/A")
                        date_modified = cdata.get("dateModified", "N/A")

                        # JSON notes are HTML-escaped JSON in a <div>.
                        parsed_data = decode_json_note(note_full)
                        is_json = parsed_data is not None
                        raw_json = json.dumps(parsed_data) if is_json else note_full

                        if args.full_notes:
                            console.print(
                                f"  - [cyan]Note[/cyan] ({safe_markup(ckey)}) [dim]Added: {date_added} | Mod: {safe_markup(date_modified)}[/dim]"
                            )
                            if is_json:
                                from rich.json import JSON

                                console.print(Panel(JSON(raw_json), border_style="cyan"))
                            else:
                                console.print(Panel(safe_markup(note_full), border_style="cyan"))
                        else:
                            if is_json:
                                display_content = json.dumps(
                                    parsed_data, indent=2, ensure_ascii=False
                                )
                            else:
                                display_content = note_full

                            note_snippet = display_content[:150].replace("\n", " ")
                            console.print(
                                f"  - [cyan]Note[/cyan] ({safe_markup(ckey)}) [dim]Added: {date_added} | Mod: {safe_markup(date_modified)}[/dim]\n"
                                f"    {escape(note_snippet)}..."
                            )
                    else:
                        filename = cdata.get("filename") or "N/A"
                        console.print(
                            f"  - [green]Attachment[/green] ({safe_markup(ckey)}): {escape(filename)}"
                        )

        if missing:
            # Shown items first, then a non-zero exit naming the rest (#368).
            raise NotFound(f"Item(s) not found: {', '.join(missing)}")


def add_inspect_verb(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:

    # Inspect
    inspect_p = sub.add_parser("inspect", help=InspectCommand.help)
    InspectCommand().register_args(inspect_p)
