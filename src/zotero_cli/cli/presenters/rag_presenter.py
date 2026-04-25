import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Sequence

from rich.console import Console
from rich.panel import Panel

from zotero_cli.core.models import SearchResult

console = Console()


class SearchResultPresenter(ABC):
    """
    Interface for presenting RAG search results in different formats.
    """

    @abstractmethod
    def present(self, results: Sequence[SearchResult]):
        pass


class HumanPresenter(SearchResultPresenter):
    """
    Renders results in a beautiful, human-readable format using Rich.
    """

    def present(self, results: Sequence[SearchResult]):
        if not results:
            console.print("[yellow]No relevant snippets found.[/yellow]")
            return

        for i, res in enumerate(results, 1):
            meta = res.metadata
            cit_key = meta.get("citation_key") or res.item_key
            qa_score = meta.get("qa_score", "N/A")
            phase = meta.get("phase_folder", "unknown")

            title = res.item.title if res.item else "Unknown Title"

            header = f"[bold cyan][{i}] {cit_key}[/bold cyan] | Score: {res.score:.4f} | QA: {qa_score} | Phase: {phase}"

            content = f"[italic white]{title}[/italic white]\n\n{res.text}"

            console.print(Panel(content, title=header, border_style="blue"))


class JsonPresenter(SearchResultPresenter):
    """
    Generates the 'Evidence Pack' in structured JSON for audit and automation.
    """

    def present(self, results: Sequence[SearchResult]):
        output = []
        for res in results:
            item_data: Dict[str, Any] = {
                "item_key": res.item_key,
                "text": res.text,
                "relevance_score": res.score,
                "metadata": res.metadata,
            }
            if res.item:
                item_data["item"] = {
                    "title": res.item.title,
                    "version": res.item.version,
                    "tags": res.item.tags,
                }
            output.append(item_data)

        print(json.dumps(output, indent=2))


class ContextPresenter(SearchResultPresenter):
    """
    Prepares a tagged text block optimized for direct LLM ingestion.
    """

    def present(self, results: Sequence[SearchResult]):
        print("[CITED_EVIDENCE_START]")
        for i, res in enumerate(results, 1):
            meta = res.metadata
            cit_key = meta.get("citation_key") or res.item_key
            qa_score = meta.get("qa_score", "N/A")

            print(f"SOURCE_ID: {i}")
            print(f"CITATION_KEY: {cit_key}")
            print(f"QUALITY_SCORE: {qa_score}")
            print(f"TEXT: {res.text}")
            print("-" * 20)
        print("[CITED_EVIDENCE_END]")
