import argparse
import sys

from rich.console import Console

from zotero_cli.core.services.slr.orchestrator import SLROrchestrator
from zotero_cli.infra.factory import GatewayFactory

console = Console()

class PromoteCommand:
    """
    CLI command to record a screening decision AND move the item to the correct folder
    in a single atomic transaction.
    """

    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        parser.description = "Records a decision and automatically moves the paper into the phase folder."
        parser.add_argument("--key", required=True, help="Item Key (ZoteroID)")
        parser.add_argument("--vote", required=True, choices=["INCLUDE", "EXCLUDE"], help="Screening decision")
        parser.add_argument("--phase", required=True,
                          choices=["title_abstract", "full_text", "quality_assessment", "data_extraction"],
                          help="SLR phase being voted on")
        parser.add_argument("--tree", required=True, help="Root collection name or key (e.g. raw_acm)")
        parser.add_argument("--code", help="Reason code (required for EXCLUDE)")
        parser.add_argument("--reason", help="Detailed reason text")
        parser.add_argument("--persona", default="unknown", help="Researcher name (e.g. Paula)")

    @staticmethod
    def execute(args: argparse.Namespace):
        if args.vote == "EXCLUDE" and not args.code:
            console.print("[bold red]Error:[/bold red] --code is required for EXCLUDE decisions.")
            sys.exit(1)

        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
        orchestrator = SLROrchestrator(gateway)
        screening_service = GatewayFactory.get_screening_service(force_user=force_user)

        # 1. Resolve folders
        root_key = gateway.get_collection_id_by_name(args.tree) or args.tree
        source_key, target_key = orchestrator.get_promotion_path(root_key, args.phase)

        if not target_key:
            console.print(f"[bold red]Error:[/bold red] Could not resolve folders for phase '{args.phase}' in tree '{args.tree}'.")
            return

        # 2. Record Decision
        # Note: ScreeningService internally handles tags and SDB note creation
        with console.status(f"[bold green]Recording {args.vote} decision..."):
            # If accepted, we set source/target for auto-move
            # If rejected, we don't move (it stays in source)
            move_source = source_key if args.vote == "INCLUDE" else None
            move_target = target_key if args.vote == "INCLUDE" else None

            success = screening_service.record_decision(
                item_key=args.key,
                decision=args.vote,
                code=args.code or "",
                reason=args.reason,
                source_collection=move_source,
                target_collection=move_target,
                persona=args.persona,
                phase=args.phase
            )

        if success:
            action = "moved to " + args.phase if args.vote == "INCLUDE" else "retained in current folder"
            console.print(f"[bold green]Success:[/bold green] Decision recorded for {args.key} and item {action}.")
        else:
            console.print(f"[bold red]Failure:[/bold red] Could not record decision for {args.key}.")
