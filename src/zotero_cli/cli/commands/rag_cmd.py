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

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/rag_ingest.md
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
        query_p.add_argument("--verify", action="store_true", help="Verify results against RAG Verification Spec v1.1")

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

        # purge
        purge_p = sub.add_parser(
            "purge",
            help="Remove indexed data from the vector store",
            description="Clears specific or all indexed data from the local vector database to manage storage and ensure data freshness.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Resetting the entire RAG system
Problem: I want to clear all data and start over with a fresh indexing strategy.
Action:  zotero-cli rag purge --all
Result:  The vector_chunks table is completely emptied.

Scenario: Updating index for a specific collection
Problem: I have updated the PDFs in my "RanSMAP" collection and want to re-index it cleanly.
Action:  zotero-cli rag purge --collection "RanSMAP" && zotero-cli rag ingest --collection "RanSMAP"
Result:  Existing chunks for RanSMAP are cleared before new ones are added.

Cognitive Safeguards
--------------------
• Common Failure Modes: Forgetting to re-ingest data after a purge, leading to empty search results.
• Safety Tips: Purge operations are irreversible. Use with caution.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/rag_purge.md
""",
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
        from zotero_cli.core.models import ZoteroQuery

        force_user = getattr(args, "user", False)
        rag_service = GatewayFactory.get_rag_service(force_user=force_user)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        if args.verb == "ingest":
            mode_desc = []
            
            # Selection Strategy [SPEC-RAG-001]
            query = ZoteroQuery()
            if args.collection:
                col_id = gateway.get_collection_id_by_name(args.collection) or args.collection
                query.item_type = "-attachment" # Exclude attachments from main search
                # Currently search_items might not support collection filter directly in ZoteroQuery 
                # but we can get items in collection
                mode_desc.append(f"collection '{args.collection}'")
                items = list(gateway.get_items_in_collection(col_id))
            elif args.key:
                mode_desc.append(f"item '{args.key}'")
                item = gateway.get_item(args.key)
                items = [item] if item else []
            else:
                mode_desc.append("entire library")
                items = list(gateway.get_all_items())

            # Filter by tag if approved_only [SPEC-RAG-001]
            if args.approved:
                mode_desc.append("approved items")
                items = [item for item in items if "rsl:include" in item.tags]
            
            if args.qa_limit is not None:
                mode_desc.append(f"QA limit >= {args.qa_limit}")

            item_keys = [item.key for item in items]
            final_desc = " + ".join(mode_desc)
            
            if args.prune:
                console.print("[bold red]Pruning vector store before start...[/bold red]")

            console.print(f"[bold]Streaming ingestion for {len(item_keys)} items...[/bold]")

            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                # Atomic Progress [SPEC-RAG-004]
                task = progress.add_task("Ingesting...", total=len(item_keys))

                def on_item(item):
                    progress.update(task, advance=1, description=f"Ingesting: {item.key}")

                stats = rag_service.ingest(
                    item_keys=item_keys,
                    prune=args.prune,
                    min_qa_score=args.qa_limit,
                    on_item_processed=on_item
                )

            console.print("[green]Ingestion complete.[/green]")
            console.print(f"  - [bold]Processed:[/bold] {stats.get('processed', 0)} items")
            if stats.get("skipped_no_text"):
                console.print(f"  - [yellow]Skipped (No PDF/Text):[/yellow] {stats['skipped_no_text']}")
            if stats.get("skipped_not_approved"):
                console.print(f"  - [yellow]Skipped (Not Approved):[/yellow] {stats['skipped_not_approved']}")
            if stats.get("skipped_low_qa"):
                console.print(f"  - [yellow]Skipped (Low QA Score):[/yellow] {stats['skipped_low_qa']}")

        elif args.verb == "query":
            if not args.json:
                console.print(f"[bold]Querying vector store for:[/bold] '{args.prompt}'")

            from typing import Sequence

            from zotero_cli.core.models import SearchResult, VerifiedSearchResult

            raw_results = rag_service.query(args.prompt, top_k=args.top_k)
            results: Sequence[SearchResult] = raw_results

            if args.verify:
                if not args.json:
                    console.print("[bold yellow]Verifying results...[/bold yellow]")
                results = rag_service.verify_results(raw_results)

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

            table = Table(title=f"Semantic Search Results (Top {args.top_k})", min_width=120)
            table.add_column("Score", justify="right", style="cyan")
            table.add_column("Title", style="green")
            table.add_column("Verified", justify="center")
            table.add_column("Authors", style="yellow")
            table.add_column("Snippet", overflow="fold")

            for res in results:
                # Clean snippet for display
                snippet = res.text[:200].replace("\n", " ").strip() + "..."
                title = res.item.title if res.item else "Unknown Title"
                authors = (
                    ", ".join(res.item.authors) if res.item and res.item.authors else "Unknown"
                )

                verified_str = "[green]Yes[/green]"
                if isinstance(res, VerifiedSearchResult):
                    if not res.is_verified:
                        verified_str = f"[red]No ({', '.join(res.verification_errors)})[/red]"
                else:
                    verified_str = "[grey]N/A[/grey]"

                table.add_row(f"{res.score:.4f}", title, verified_str, authors, snippet)

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

        elif args.verb == "purge":
            if args.all:
                console.print("[bold red]Purging all data from vector store...[/bold red]")
                rag_service.purge(purge_all=True)
                console.print("[green]Vector store cleared.[/green]")
            elif args.key:
                console.print(f"Purging data for item [cyan]{args.key}[/cyan]...")
                rag_service.purge(item_key=args.key)
                console.print(f"[green]Item {args.key} cleared from vector store.[/green]")
            elif args.collection:
                console.print(f"Purging data for collection [cyan]{args.collection}[/cyan]...")
                stats = rag_service.purge(collection_key=args.collection)
                console.print(
                    f"[green]Collection {args.collection} cleared ({stats.get('items_cleared', 0)} items processed).[/green]"
                )
