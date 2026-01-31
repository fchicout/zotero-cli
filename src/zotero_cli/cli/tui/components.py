from typing import List, Optional

from rich.panel import Panel
from rich.text import Text


def create_abstract_panel(
    title: Optional[str],
    authors: List[str],
    date: Optional[str],
    abstract: Optional[str],
    border_style: str = "green",
) -> Panel:
    """
    Creates a standardized panel for displaying paper metadata and abstract.
    """
    title_text = Text(title if title else "No Title", style="bold cyan")
    authors_snippet = ", ".join(authors[:3])
    if len(authors) > 3:
        authors_snippet += " et al."

    meta_text = Text(f"\nYear: {date} | Authors: {authors_snippet}", style="yellow")
    abstract_text = Text(f"\n\n{abstract if abstract else 'No Abstract'}", style="white")

    content = Text.assemble(title_text, meta_text, abstract_text)
    return Panel(content, title="Abstract", border_style=border_style)


def create_header_panel(text: str, style: str = "white on blue") -> Panel:
    return Panel(text, style=style)


def create_footer_panel(controls: str, style: str = "white on blue") -> Panel:
    return Panel(controls, style=style)
