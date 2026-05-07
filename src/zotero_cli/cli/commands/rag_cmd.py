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
        query_p.add_argument(
            "--ask", "--synthesize",
            dest="synthesize",
            action="store_true",
            help="Synthesize a meaningful answer using the configured LLM (Gemini/OpenAI)"
        )

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

        # model
        model_p = sub.add_parser(
            "model",
            help="Manage embedding models",
            description="Operations related to model selection, downloading, and cleanup.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        model_sub = model_p.add_subparsers(dest="model_verb", required=True)

        # model set
        model_sub.add_parser(
            "set",
            help="Select and download the embedding model",
        )

        # model clean
        model_sub.add_parser(
            "clean",
            help="Remove all downloaded embedding models from disk",
        )

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
            # ...
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

                def on_item(item, total):
                    progress.update(task, total=total, advance=1, description=f"Ingesting: {item.key}")

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

            if getattr(args, "synthesize", False):
                console.print("[bold cyan]Synthesizing meaningful answer...[/bold cyan]")
                summary = rag_service.synthesize(args.prompt, list(results))

                from rich.markdown import Markdown
                from rich.panel import Panel
                console.print(Panel(Markdown(summary), title="Synthesized Answer", border_style="cyan"))
                console.print("\n[bold dim]Supporting Evidence:[/bold dim]")

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

        elif args.verb == "model":
            if args.model_verb == "set":
                self._execute_set_model()
            elif args.model_verb == "clean":
                self._execute_clean_model()

    def _execute_clean_model(self):
        import os
        import shutil

        from huggingface_hub import scan_cache_dir
        from rich.prompt import Confirm

        console.print("[bold red]Model Cleanup Utility[/bold red]")
        console.print("Scanning Hugging Face cache...")

        try:
            cache_info = scan_cache_dir()
            total_size = cache_info.size_on_disk_str

            console.print(f"Current HF cache usage: [bold blue]{total_size}[/bold blue]")

            if not cache_info.repos:
                console.print("[yellow]No models found in cache.[/yellow]")
                return

            confirm = Confirm.ask("Delete ALL cached models and modules? [bold red]This cannot be undone.[/bold red]")
            if not confirm:
                console.print("[yellow]Cleanup cancelled.[/yellow]")
                return

            # Option 1: Clean via library (safer)
            # Option 2: Blunt wipe (faster for user space)
            # We will use the scan info to target specifically the Hub and Modules

            count = 0
            for repo in cache_info.repos:
                # We could filter for specific names, but user requested 'remove all downloaded'
                # hub cache delete
                shutil.rmtree(repo.repo_path, ignore_errors=True)
                count += 1

            # Also clean dynamic modules (where the broken Jina files were)
            module_cache = os.path.expanduser("~/.cache/huggingface/modules")
            if os.path.exists(module_cache):
                shutil.rmtree(module_cache, ignore_errors=True)
                console.print("[dim]Dynamic modules cleared.[/dim]")

            console.print(f"[green]Successfully removed {count} model repositories.[/green]")
            console.print("[yellow]Note: The next RAG operation will require a new model download.[/yellow]")

        except Exception as e:
            console.print(f"[bold red]Error during cleanup:[/bold red] {e}")

    def _execute_set_model(self):
        from rich.prompt import Prompt
        from rich.table import Table

        from zotero_cli.core.config import ConfigManager, get_config

        # 1. Selection for Embedding Model (The Finder)
        EMB_MODELS = {
            "1": {"name": "BGE-M3 (Most Stable / Hybrid)", "id": "BAAI/bge-m3", "size": "~1.1GB"},
            "2": {"name": "Jina v3 (High Efficiency)", "id": "jinaai/jina-embeddings-v3", "size": "~1.2GB"},
            "3": {"name": "Qwen2-7B (Maximum Accuracy)", "id": "Alibaba-NLP/gte-Qwen2-7B-instruct", "size": "~15GB"},
        }

        table = Table(title="Stage 1: Embedding Models (Search)")
        table.add_column("Option", style="cyan")
        table.add_column("Model Name", style="green")
        table.add_column("Hugging Face ID", style="blue")
        table.add_column("Estimated Size", style="magenta")

        for k, v in EMB_MODELS.items():
            table.add_row(k, v["name"], v["id"], v["size"])

        console.print(table)
        choice_emb = Prompt.ask("Choose an Embedding model", choices=list(EMB_MODELS.keys()), default="1")
        selected_emb = EMB_MODELS[choice_emb]

        # 2. Selection for Generative Model (The Writer)
        GEN_MODELS = {
            "1": {"name": "Qwen2.5-1.5B (Tiny/Fast)", "id": "Qwen/Qwen2.5-1.5B-Instruct", "size": "~3GB"},
            "2": {"name": "Llama-3.2-3B (Balanced)", "id": "meta-llama/Llama-3.2-3B-Instruct", "size": "~6GB"},
            "3": {"name": "None (Use Gemini/OpenAI API)", "id": "auto", "size": "0GB"},
        }

        console.print("\n")
        table_gen = Table(title="Stage 2: Generative Models (Synthesis)")
        table_gen.add_column("Option", style="cyan")
        table_gen.add_column("Model Name", style="green")
        table_gen.add_column("Hugging Face ID", style="blue")
        table_gen.add_column("Estimated Size", style="magenta")

        for k, v in GEN_MODELS.items():
            table_gen.add_row(k, v["name"], v["id"], v["size"])

        console.print(table_gen)
        choice_gen = Prompt.ask("Choose a Generative model", choices=list(GEN_MODELS.keys()), default="1")
        selected_gen = GEN_MODELS[choice_gen]

        console.print("\nFinal Selection:")
        console.print(f"  - Embedding: [bold]{selected_emb['name']}[/bold]")
        console.print(f"  - Generative: [bold]{selected_gen['name']}[/bold]")

        confirm = Prompt.ask("\nUpdate configuration and download models?", choices=["y", "n"], default="y")
        if confirm != "y":
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        # 1. Update Config
        config = get_config()
        manager = ConfigManager()
        updates = {
            "embedding_model": selected_emb["id"],
            "embedding_provider": "local"
        }

        if selected_gen["id"] != "auto":
            updates["generative_model"] = selected_gen["id"]
            updates["generative_provider"] = "local"
        else:
            updates["generative_provider"] = "auto"

        manager.update_config(updates)
        console.print("[green]Configuration updated.[/green]")

        # 2. Download Models
        try:
            from huggingface_hub import snapshot_download

            # Download Embedding
            console.print(f"Downloading Embedding Model: {selected_emb['id']}...")
            snapshot_download(
                repo_id=selected_emb["id"], token=config.huggingface_token
            )

            # Download Generative (if not API)
            if selected_gen["id"] != "auto":
                console.print(f"Downloading Generative Model: {selected_gen['id']}...")
                snapshot_download(
                    repo_id=selected_gen["id"], token=config.huggingface_token
                )


            console.print("[green]All models downloaded and cached.[/green]")

        except Exception as e:
            console.print(f"[bold red]Error downloading model:[/bold red] {e}")
            if "GatedRepoError" in str(type(e)):
                console.print("[yellow]Hint: Some models (like Llama) are gated. Ensure you have accepted terms and your token is valid.[/yellow]")
