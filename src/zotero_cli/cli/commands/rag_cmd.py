import argparse
import json
from dataclasses import asdict

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
        ingest_p = sub.add_parser(
            "ingest",
            help="Ingest papers into the vector store",
            description="Populates the local vector database with the text content of papers from a Zotero collection, enabling semantic search and context retrieval.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Preparing a collection for semantic analysis
Problem: I have a collection of 50 papers and I want to ask questions about their specific implementation details.
Action:  zotero-cli rag ingest --collection "Transformer Papers"
Result:  The CLI extracts text, generates embeddings, and indexes them. They are now searchable via rag query.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to ingest items without local PDF attachments.
• Safety Tips: Ingestion is computationally expensive. For very large collections, process in batches.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/rag_ingest.md
""",
        )
        ingest_p.add_argument("--collection", required=True, help="Collection name or key")

        # query
        query_p = sub.add_parser(
            "query",
            help="Semantic search against the vector store",
            description="Performs a semantic search across your indexed Zotero library to find the most relevant text snippets based on a natural language prompt.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Finding implementation details across a library
Problem: I know I have papers that discuss "Layer Normalization" in Transformers, but I don't remember which ones.
Action:  zotero-cli rag query "How is Layer Normalization applied in Transformer blocks?" --top-k 3
Result:  The CLI returns the 3 most relevant paragraphs from different papers with source citations.

Cognitive Safeguards
--------------------
• Common Failure Modes: Running a query before ingesting any data.
• Safety Tips: Semantic search is probabilistic. High scores indicate strong matches, but always verify context.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/rag_query.md
""",
        )
        query_p.add_argument("prompt", help="Search prompt/query")
        query_p.add_argument("--top-k", type=int, default=5, help="Number of results (Default: 5)")
        query_p.add_argument("--json", action="store_true", help="Output results in JSON format")

        # context
        context_p = sub.add_parser(
            "context",
            help="Retrieve context snippets for an item",
            description="Aggregates all textual snippets and metadata belonging to a specific item to reconstruct its original context for LLM ingestion.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Summarizing a single paper via LLM
Problem: I want to generate a 500-word summary of a specific paper in my collection using a local LLM.
Action:  zotero-cli rag context --key "W2A3B4C5" > paper_context.txt
Result:  The file paper_context.txt contains the full text of the paper. This can be piped to an LLM prompt.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to retrieve context for an item that has not been ingested.
• Safety Tips: Context outputs can be very large. Ensure the total length doesn't exceed the model's token limit.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/rag_context.md
""",
        )
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
            if not args.json:
                console.print(f"[bold]Querying vector store for:[/bold] '{args.prompt}'")

            results = rag_service.query(args.prompt, top_k=args.top_k)

            if not results:
                if not args.json:
                    console.print("[yellow]No relevant snippets found.[/yellow]")
                else:
                    print(json.dumps([]))
                return

            if args.json:
                # Issue #110: Serialize full untruncated text and item metadata
                output = []
                for res in results:
                    res_dict = asdict(res)
                    # asdict might be recursive, but let's be safe with ZoteroItem
                    output.append(res_dict)
                print(json.dumps(output, indent=2))
                return

            table = Table(title=f"Semantic Search Results (Top {args.top_k})")
            table.add_column("Score", justify="right", style="cyan")
            table.add_column("Title", style="green")
            table.add_column("Authors", style="yellow")
            table.add_column("Snippet", overflow="fold")

            for res in results:
                # Clean snippet for display
                snippet = res.text[:200].replace("\n", " ").strip() + "..."
                title = res.item.title if res.item else "Unknown Title"
                authors = ", ".join(res.item.authors) if res.item and res.item.authors else "Unknown"

                table.add_row(f"{res.score:.4f}", title, authors, snippet)

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
