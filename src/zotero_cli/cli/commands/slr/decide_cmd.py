import argparse
import sys

from rich.console import Console

from zotero_cli.infra.factory import GatewayFactory

console = Console()

class DecideCommand:
    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        parser.add_argument("--key", required=True, help="Item Key")
        parser.add_argument("--vote", choices=["INCLUDE", "EXCLUDE"], help="Screening decision")
        parser.add_argument("--code", help="Reason code (required for EXCLUDE)")
        parser.add_argument("--reason", help="Detailed reason text")
        parser.add_argument("--source", help="Source collection")
        parser.add_argument("--target", help="Target collection")
        parser.add_argument("--agent-led", action="store_true", help="Run in Agent-led mode")
        parser.add_argument("--persona", help="Reviewer persona")
        parser.add_argument("--phase", default="title_abstract", help="Review phase")
        parser.add_argument("--evidence", help="Evidence text for decision")
        # Quick flags for common exclusion reasons
        parser.add_argument("--short-paper", help="Exclusion code for short papers")
        parser.add_argument("--not-english", help="Exclusion code for non-English papers")
        parser.add_argument("--is-survey", help="Exclusion code for surveys/SLRs")
        parser.add_argument("--no-pdf", help="Exclusion code for missing PDFs")

    @staticmethod
    def execute(args: argparse.Namespace):
        service = GatewayFactory.get_screening_service(force_user=getattr(args, "user", False))
        vote = args.vote
        code = args.code
        reason = args.reason

        if args.short_paper:
            vote, code, reason = "EXCLUDE", args.short_paper, "Short Paper"
        elif args.not_english:
            vote, code, reason = "EXCLUDE", args.not_english, "Not English"
        elif args.is_survey:
            vote, code, reason = "EXCLUDE", args.is_survey, "SLR/Survey"
        if args.no_pdf:
            vote, code, reason = "EXCLUDE", args.no_pdf, "No PDF"

        if not vote:
            console.print("[bold red]Error:[/bold red] You must provide --vote.")
            sys.exit(1)

        if vote == "EXCLUDE" and not code:
            console.print(
                "[bold red]Error:[/bold red] You must provide --code for EXCLUDE decisions."
            )
            sys.exit(1)

        agent_name = args.persona if args.agent_led else "human"
        success = service.record_decision(
            item_key=args.key,
            decision=vote,
            code=code,
            reason=reason,
            source_collection=args.source,
            target_collection=args.target,
            agent="zotero-cli",
            persona=agent_name,
            phase=args.phase,
            evidence=args.evidence,
        )
        if success:
            print(f"Successfully recorded decision for {args.key} ({vote}: {reason})")
        else:
            print(f"Failed to record decision for {args.key}")
            sys.exit(1)
