import argparse
import json

from rich.console import Console
from rich.panel import Panel

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.infra.factory import GatewayFactory

console = Console()


@CommandRegistry.register
class InspectCommand(BaseCommand):
    name = "inspect"
    help = "Inspect item details"

    def register_args(self, parser: argparse.ArgumentParser):
        parser.add_argument('key', help='Zotero Item Key')
        parser.add_argument('--raw', action='store_true', help='Show raw JSON')
        parser.add_argument('--full-notes', action='store_true', help='Show full content of child notes')

    def execute(self, args: argparse.Namespace):
        gateway = GatewayFactory.get_zotero_gateway(force_user=getattr(args, 'user', False))

        item = gateway.get_item(args.key)
        if not item:
            console.print(f"[bold red]Item '{args.key}' not found.[/bold red]")
            return

        if args.raw:
            print(json.dumps(item.raw_data, indent=2))
            return

        console.print(Panel(f"[bold]Title:[/bold] {item.title}\n" \
                           f"[bold]Type:[/bold] {item.item_type}\n" \
                           f"[bold]Date:[/bold] {item.date}\n" \
                           f"[bold]Authors:[/bold] {', '.join(item.authors)}\n" \
                           f"[bold]DOI:[/bold] {item.doi}\n" \
                           f"[bold]URL:[/bold] {item.url}\n\n" \
                           f"[bold]Abstract:[/bold]\n{item.abstract}",
                           title=f"Item: {args.key}"))

        # Children (Notes/Attachments)
        children = gateway.get_item_children(args.key)
        if children:
            console.print(f"\n[bold]Children ({len(children)}):[/bold]")
            for child in children:
                ctype = child.get('data', {}).get('itemType', 'unknown')
                ckey = child.get('key')
                if ctype == 'note':
                    note_full = child.get('data', {}).get('note', '')
                    if args.full_notes:
                        console.print(f"  - [cyan]Note[/cyan] ({ckey}):")
                        console.print(Panel(note_full, border_style="cyan"))
                    else:
                        note_snippet = note_full[:100].replace('\n', ' ')
                        console.print(f"  - [cyan]Note[/cyan] ({ckey}): {note_snippet}...")
                else:
                    filename = child.get('data', {}).get('filename', 'N/A')
                    console.print(f"  - [green]Attachment[/green] ({ckey}): {filename}")
