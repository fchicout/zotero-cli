import argparse
import asyncio

from rich.console import Console
from rich.markup import escape

from zotero_cli.cli.tui.factory import TUIFactory
from zotero_cli.core.config import ZoteroConfig, get_config
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.infra.factory import GatewayFactory

console = Console()


class SnowballCommand:
    @staticmethod
    def register_args(parser: argparse.ArgumentParser) -> None:
        snow_sub = parser.add_subparsers(dest="snow_verb", required=True)

        # seed
        seed_p = snow_sub.add_parser("seed", help="Enqueue starting DOIs for discovery")
        seed_p.add_argument("--keys", help="Comma-separated Zotero keys")
        seed_p.add_argument("--collection", help="Collection name or key")
        seed_p.add_argument("--dois", help="Comma-separated bare DOIs (no Zotero lookup)")
        seed_p.add_argument(
            "--from-accepted",
            action="store_true",
            help=(
                "Seed from this discovery graph's own ACCEPTED candidates "
                "(not yet imported into Zotero) - use --from-generation to "
                "scope it to a single prior generation"
            ),
        )
        seed_p.add_argument(
            "--from-generation",
            type=int,
            help="With --from-accepted, only use candidates accepted at this generation",
        )
        seed_p.add_argument("--backward", action="store_true", help="Fetch references (CrossRef)")
        seed_p.add_argument(
            "--forward", action="store_true", help="Fetch citations (Semantic Scholar)"
        )
        seed_p.add_argument(
            "--generation", type=int, default=1, help="Graph generation (Default: 1)"
        )

        # discovery
        disc_p = snow_sub.add_parser("discovery", help="Run background workers to process jobs")
        disc_p.add_argument("--count", type=int, help="Number of jobs to process")

        # review
        snow_sub.add_parser("review", help="Interactive Review Interface (TUI)")

        # import
        import_p = snow_sub.add_parser("import", help="Import ACCEPTED candidates to Zotero")
        import_p.add_argument("--target", required=True, help="Target collection name")
        import_p.add_argument("--create", action="store_true", help="Create collection if missing")

        # status
        snow_sub.add_parser("status", help="Show discovery graph statistics")

        # export
        export_p = snow_sub.add_parser("export", help="Export discovery graph")
        export_p.add_argument(
            "--format", choices=["json", "mermaid"], default="mermaid", help="Export format"
        )
        export_p.add_argument("--output", help="Output file path")

    @staticmethod
    def execute(gateway: ZoteroGateway, args: argparse.Namespace) -> None:
        force_user = getattr(args, "user", False)
        # Resolved once and threaded through every snowball-graph-service
        # call site below (Issue #228): the discovery graph is scoped per
        # active library, so every verb in this command must agree on the
        # same config - otherwise `discovery`/`seed` could write to one
        # library's graph file while `review`/`status`/`export` read
        # another's.
        config = get_config(getattr(args, "config", None))

        if args.snow_verb == "seed":
            SnowballCommand._handle_seed(gateway, args, force_user, config)
        elif args.snow_verb == "discovery":
            worker = GatewayFactory.get_snowball_worker(config, force_user=force_user)
            console.print("[bold]Starting Snowballing Discovery Workers...[/bold]")
            asyncio.run(worker.process_jobs(count=args.count))
            console.print("[bold green]Done.[/bold green]")
        elif args.snow_verb == "review":
            graph_service = GatewayFactory.get_snowball_graph_service(
                config, force_user=force_user
            )
            metadata_service = GatewayFactory.get_metadata_aggregator(config)
            tui = TUIFactory.get_snowball_tui(graph_service, metadata_service, gateway)
            tui.run_review_session()
        elif args.snow_verb == "import":
            SnowballCommand._handle_import(gateway, args, force_user, config)
        elif args.snow_verb == "status":
            SnowballCommand._handle_status(config, force_user)
        elif args.snow_verb == "export":
            SnowballCommand._handle_export(args, config, force_user)

    @staticmethod
    def _handle_seed(
        gateway: ZoteroGateway, args: argparse.Namespace, force_user: bool, config: ZoteroConfig
    ) -> None:
        from zotero_cli.core.services.snowball_worker import SnowballDiscoveryWorker

        job_queue = GatewayFactory.get_job_queue_service(config, force_user=force_user)
        dois = []
        if args.keys:
            for key in args.keys.split(","):
                item = gateway.get_item(key.strip())
                if item and item.doi:
                    dois.append(item.doi)
        if args.collection:
            col_id = gateway.get_collection_id_by_name(args.collection)
            if col_id:
                items = gateway.get_items_in_collection(col_id)
                for item in items:
                    if item.doi:
                        dois.append(item.doi)
        if getattr(args, "dois", None):
            dois.extend(doi.strip() for doi in args.dois.split(",") if doi.strip())
        if getattr(args, "from_accepted", False):
            graph_service = GatewayFactory.get_snowball_graph_service(
                config, force_user=force_user
            )
            dois.extend(
                graph_service.get_accepted_dois(generation=getattr(args, "from_generation", None))
            )
        if not dois:
            console.print("[yellow]No items with DOIs found to process.[/yellow]")
            return
        enqueued = 0
        for doi in dois:
            if args.backward:
                job_queue.enqueue(
                    doi, SnowballDiscoveryWorker.TASK_BACKWARD, {"generation": args.generation}
                )
                enqueued += 1
            if args.forward:
                job_queue.enqueue(
                    doi, SnowballDiscoveryWorker.TASK_FORWARD, {"generation": args.generation}
                )
                enqueued += 1
        console.print(f"[green]Enqueued {enqueued} discovery jobs.[/green]")

    @staticmethod
    def _handle_import(
        gateway: ZoteroGateway, args: argparse.Namespace, force_user: bool, config: ZoteroConfig
    ) -> None:
        service = GatewayFactory.get_snowball_ingestion_service(config, force_user=force_user)
        col_id = gateway.get_collection_id_by_name(args.target)
        if not col_id:
            if args.create:
                console.print(f"Collection '{escape(args.target)}' not found. Creating...")
                col_id = gateway.create_collection(args.target)
            else:
                console.print(
                    f"[red]Error: Collection '{escape(args.target)}' not found. "
                    "Use --create to create it.[/red]"
                )
                return
        if col_id:
            console.print(
                f"[bold]Ingesting ACCEPTED candidates into '{escape(args.target)}'...[/bold]"
            )
            with console.status("[bold green]Working..."):
                stats = service.ingest_candidates(args.target)
            console.print(f"[green]Ingestion Complete: {stats['imported']} imported.[/green]")

    @staticmethod
    def _handle_status(config: ZoteroConfig, force_user: bool = False) -> None:
        graph_service = GatewayFactory.get_snowball_graph_service(config, force_user=force_user)
        stats = graph_service.get_stats()
        console.print("\n[bold blue]Snowballing Discovery Graph Status[/bold blue]\n")
        console.print(f"Total Papers (Nodes): {stats['total_nodes']}")
        console.print(f"Total Citations (Edges): {stats['total_edges']}")
        # Additional tables could be added here...

    @staticmethod
    def _handle_export(
        args: argparse.Namespace, config: ZoteroConfig, force_user: bool = False
    ) -> None:
        graph_service = GatewayFactory.get_snowball_graph_service(config, force_user=force_user)
        if args.format == "json":
            output = graph_service.to_json()
        else:
            output = graph_service.to_mermaid()

        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            console.print(f"[green]Graph exported to {args.output}[/green]")
        else:
            # markup=False: JSON/Mermaid node labels routinely contain
            # literal "[...]" (paper titles, mermaid's own node syntax),
            # which Rich would otherwise try to parse as markup tags and
            # silently mangle.
            console.print(output, markup=False)
