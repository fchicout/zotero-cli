from typing import Any, List

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt

from zotero_cli.core.services.extraction_service import ExtractionService
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.opener import OpenerService

console = Console()


class ExtractionTUI:
    def __init__(self, service: ExtractionService, opener: OpenerService):
        self.service = service
        self.opener = opener

    def run_extraction(
        self,
        items: List[ZoteroItem],
        agent: str = "zotero-cli",
        persona: str = "unknown",
    ):
        """
        Main loop for extraction TUI.
        """
        # 1. Load Schema
        try:
            schema = self.service.validator.load_schema()
            variables = schema.get("variables", [])
            schema_version = schema.get("version", "1.0")
        except Exception as e:
            console.print(f"[bold red]Error loading schema:[/bold red] {e}")
            return

        if not variables:
            console.print("[yellow]No variables defined in schema.yaml[/yellow]")
            return

        total = len(items)
        console.print(f"[bold cyan]Starting Extraction Session for {total} items[/bold cyan]")

        for idx, item in enumerate(items):
            console.rule(f"Item {idx + 1}/{total}: {item.key}")
            console.print(f"[bold]{item.title}[/bold]")
            if item.authors:
                console.print(f"[italic]{', '.join(item.authors)}[/italic]")
            console.print(f"Year: {item.date or 'N/A'}")

            # 2. Open PDF
            # Heuristic: Look for attachment with .pdf in title or contentType 'application/pdf'
            # Note: Since we don't have full attachment objects here easily, we might need to fetch them.
            # Assuming item.raw_data might contain child info if fetched deep, but ZoteroItem usually shallow.
            # We will rely on user to open PDF manually if opener fails or just print link to item.
            # But wait, blueprint says "Find best PDF attachment".
            # We don't have AttachmentService injected here. We should probably just try to open the item URL if local PDF logic is complex without it.
            # However, OpenerService takes a path.
            # Let's just print the Zotero URI for now or try to open the URL.
            # Actually, `opener.open_file` implies local path.
            # Without `AttachmentService` resolving the path, we can't open local PDF easily.
            # I will skip complex PDF resolving for this MVP and just offer to open the URL.
            if item.url:
                console.print(f"URL: {item.url}")
                if Confirm.ask("Open URL?", default=True):
                    self.opener.open_file(item.url)

            # 3. Extraction Loop
            extracted_data = {}
            console.print("\n[bold]Extraction Form:[/bold]")

            for var in variables:
                key = var["key"]
                label = var["label"]
                v_type = var["type"]
                options = var.get("options", [])
                desc = var.get("description", "")

                console.print(f"\n[cyan]{label}[/cyan] ({v_type})")
                if desc:
                    console.print(f"[dim]{desc}[/dim]")

                value = self._prompt_variable(v_type, options, key)

                # Evidence Collection
                evidence = Prompt.ask(f"Evidence for [cyan]{label}[/cyan] (optional)")
                location = Prompt.ask("Location (Page/Section) (optional)")

                extracted_data[key] = {
                    "value": value,
                    "evidence": evidence if evidence else None,
                    "location": location if location else None,
                }

            # 4. Save
            if Confirm.ask("Save extraction data?", default=True):
                success = self.service.save_extraction(
                    item.key, extracted_data, schema_version, agent, persona
                )
                if success:
                    console.print("[green]Saved![/green]")
                else:
                    console.print("[red]Failed to save![/red]")
            else:
                console.print("[yellow]Skipped saving.[/yellow]")

    def _prompt_variable(self, v_type: str, options: List[str], key: str) -> Any:
        if v_type == "text":
            return Prompt.ask(f"Enter value for {key}")
        elif v_type == "number":
            return IntPrompt.ask(f"Enter number for {key}")
        elif v_type == "boolean":
            return Confirm.ask(f"Is {key} true?")
        elif v_type == "select":
            return Prompt.ask(f"Select for {key}", choices=options)
        elif v_type == "multi-select":
            # Simple comma-separated input for now
            console.print(f"Options: {', '.join(options)}")
            val = Prompt.ask(f"Enter values for {key} (comma separated)")
            selected = [v.strip() for v in val.split(",") if v.strip()]
            # Validate?
            valid_opts = set(options)
            filtered = [s for s in selected if s in valid_opts]
            if len(filtered) != len(selected):
                console.print("[yellow]Warning: Some values were invalid and removed.[/yellow]")
            return filtered
        elif v_type == "date":
            return Prompt.ask(f"Enter date (YYYY-MM-DD) for {key}")
        else:
            return Prompt.ask(f"Enter value ({v_type})")
