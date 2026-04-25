import argparse
from typing import Sequence

from rich.console import Console

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.presenters.rag_presenter import (
    ContextPresenter,
    HumanPresenter,
    JsonPresenter,
)
from zotero_cli.infra.factory import GatewayFactory

console = Console()


@CommandRegistry.register
class RAGCommand(BaseCommand):
    name = "rag"
    help = "Retrieval-Augmented Generation (RAG) Core operations"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)

        # ingest
        ingest_p = sub.add_parser(
            "ingest",
            help="Ingest papers into the vector store",
            description="Populates the local vector database with the text content of papers from Zotero, enabling semantic search and context retrieval.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Preparing a collection for semantic analysis
Problem: I have a collection of 50 papers and I want to ask questions about their specific implementation details.
Action:  zotero-cli rag ingest --collection "Transformer Papers"
Result:  The CLI extracts text, generates embeddings, and indexes them.

Scenario: Only indexing high-quality approved papers
Problem: I only want to search papers that passed screening and have a high quality score.
Action:  zotero-cli rag ingest --approved --qa-limit 0.8
Result:  Only items with 'rsl:include' tag and QA score >= 0.8 are indexed.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to ingest items without local PDF attachments.
• Safety Tips: Ingestion is computationally expensive. Use targeted modes (--key, --approved) to save resources.
""",
        )
        ingest_group = ingest_p.add_mutually_exclusive_group(required=False)
        ingest_group.add_argument("--collection", help="Collection name or key")
        ingest_group.add_argument("--key", help="Single item key")
        ingest_p.add_argument("--approved", action="store_true", help="Ingest only approved items (rsl:include)")
        ingest_p.add_argument("--qa-limit", type=float, help="Minimum extraction QA score threshold")
        ingest_p.add_argument("--prune", action="store_true", default=False, help="Clear the vector store before ingestion")
        ingest_p.add_argument("--no-prune", action="store_false", dest="prune", help="Append to the vector store (Default)")

        # query
        query_p = sub.add_parser(
            "query",
            help="Semantic search against the vector store",
            description="Performs a semantic search across your indexed Zotero library to find the most relevant text snippets based on a natural language prompt.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        query_p.add_argument("prompt", help="Search prompt/query")
        query_p.add_argument("--top-k", type=int, default=5, help="Number of results (Default: 5)")
        query_p.add_argument(
            "--format",
            choices=["human", "json", "context"],
            default="human",
            help="Output format (human: beautiful UI, json: evidence pack, context: LLM-ready context)",
        )
        query_p.add_argument("--verify", action="store_true", help="Verify results against RAG Verification Spec v1.1")

        # context
        context_p = sub.add_parser(
            "context",
            help="Retrieve context snippets for an item",
            description="Aggregates all textual snippets and metadata belonging to a specific item to reconstruct its original context for LLM ingestion.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        context_p.add_argument("--key", required=True, help="Item Key")

        # purge
        purge_p = sub.add_parser(
            "purge",
            help="Remove indexed data from the vector store",
            description="Clears specific or all indexed data from the local vector database to manage storage and ensure data freshness.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        purge_group = purge_p.add_mutually_exclusive_group(required=True)
        purge_group.add_argument("--all", action="store_true", help="Clear all indexed data")
        purge_group.add_argument("--key", help="Clear data for a specific item key")
        purge_group.add_argument("--collection", help="Clear data for an entire collection")

    def execute(self, args: argparse.Namespace):
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            TextColumn,
            TimeRemainingColumn,
        )

        force_user = getattr(args, "user", False)
        rag_service = GatewayFactory.get_rag_service(force_user=force_user)

        if args.verb == "ingest":
            if args.prune:
                console.print("[bold red]Pruning vector store before start...[/bold red]")

            # We pass the raw parameters to the service as requested in the audit
            console.print("[bold]Streaming ingestion starting...[/bold]")

            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                # Since we don't know the count yet (service resolves it),
                # we start with indeterminate or 0.
                task = progress.add_task("Ingesting...", total=None)

                def on_item(item):
                    progress.update(task, advance=1, description=f"Ingesting: {item.key}")

                stats = rag_service.ingest(
                    collection_key=args.collection,
                    item_key=args.key,
                    approved_only=args.approved,
                    prune=args.prune,
                    min_qa_score=args.qa_limit,
                    on_item_processed=on_item
                )

            console.print("[green]Ingestion complete.[/green]")
            console.print(f"  - [bold]Processed:[/bold] {stats.get('processed', 0)} items")
            if stats.get("skipped_low_qa"):
                console.print(f"  - [yellow]Skipped (Low QA Score):[/yellow] {stats['skipped_low_qa']}")

        elif args.verb == "query":
            from zotero_cli.core.models import SearchResult

            if args.format == "human":
                console.print(f"Querying vector store for: '{args.prompt}'")

            raw_results = rag_service.query(args.prompt, top_k=args.top_k)
            results: Sequence[SearchResult] = raw_results

            if args.verify:
                console.print("Verifying results...")
                results = rag_service.verify_results(raw_results)

            from zotero_cli.cli.presenters.rag_presenter import SearchResultPresenter

            # Choose Presenter
            presenter: SearchResultPresenter
            if args.format == "json":
                presenter = JsonPresenter()
            elif args.format == "context":
                presenter = ContextPresenter()
            else:
                presenter = HumanPresenter()

            presenter.present(results)

        elif args.verb == "context":
            context = rag_service.get_context(args.key)
            if context:
                console.print(context)
            else:
                console.print("[yellow]No context found for this item.[/yellow]")

        elif args.verb == "purge":
            if args.all:
                rag_service.purge(purge_all=True)
            elif args.key:
                rag_service.purge(item_key=args.key)
            elif args.collection:
                rag_service.purge(collection_key=args.collection)
            console.print("[green]Purge operation completed.[/green]")
