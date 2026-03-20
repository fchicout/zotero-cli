import argparse

from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.infra.factory import GatewayFactory

console = Console()


@CommandRegistry.register
class RAGCommand(BaseCommand):
    name = "rag"
    help = "Retrieval-Augmented Generation (RAG) Core operations"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)

        # ingest
        ingest_p = sub.add_parser("ingest", help="Ingest papers into the vector store")
        ingest_p.add_argument("--collection", required=True, help="Collection name or key")

        # query
        query_p = sub.add_parser("query", help="Semantic search against the vector store")
        query_p.add_argument("prompt", help="Search prompt/query")
        query_p.add_argument("--top-k", type=int, default=5, help="Number of results (Default: 5)")

        # context
        context_p = sub.add_parser("context", help="Retrieve context snippets for an item")
        context_p.add_argument("--key", required=True, help="Item Key")

    def execute(self, args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        rag_service = GatewayFactory.get_rag_service(force_user=force_user)

        if args.verb == "ingest":
            console.print(
                f"[bold]Ingesting collection '{args.collection}' into vector store...[/bold]"
            )
            with console.status("[bold green]Extracting text and generating embeddings..."):
                stats = rag_service.ingest_collection(args.collection)
            console.print(
                f"[green]Ingestion complete. Processed {stats['processed']} items.[/green]"
            )

        elif args.verb == "query":
            console.print(f"[bold]Querying vector store for:[/bold] '{args.prompt}'")
            results = rag_service.query(args.prompt, top_k=args.top_k)

            if not results:
                console.print("[yellow]No relevant snippets found.[/yellow]")
                return

            table = Table(title=f"Semantic Search Results (Top {args.top_k})")
            table.add_column("Score", justify="right", style="cyan")
            table.add_column("Item Key", style="magenta")
            table.add_column("Snippet", overflow="fold")

            for res in results:
                # Clean snippet for display
                snippet = res.text[:200].replace("\n", " ").strip() + "..."
                table.add_row(f"{res.score:.4f}", res.item_key, snippet)

            console.print(table)

        elif args.verb == "context":
            console.print(f"[bold]Retrieving context for item {args.key}...[/bold]")
            context = rag_service.get_context(args.key)
            if context:
                console.print("\n--- BEGIN CONTEXT ---\n")
                console.print(context)
                console.print("\n--- END CONTEXT ---\n")
            else:
                console.print("[yellow]No context found for this item. Run ingest first.[/yellow]")
