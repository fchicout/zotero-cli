import argparse
import asyncio
import os
import sys
import time
from typing import Any

from rich.console import Console
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.core.services.backup_service import BackupService
from zotero_cli.core.strategies import (
    BibtexImportStrategy,
    CanonicalCsvImportStrategy,
    IeeeCsvImportStrategy,
    RisImportStrategy,
    SpringerCsvImportStrategy,
)
from zotero_cli.infra.bibtex_lib import BibtexLibGateway
from zotero_cli.infra.canonical_csv_lib import CanonicalCsvLibGateway
from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway
from zotero_cli.infra.ris_lib import RisLibGateway
from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway

console = Console()


class InfoCommand(BaseCommand):
    name = "info"
    help = "Display environment and configuration"

    def register_args(self, parser: argparse.ArgumentParser):
        pass  # No extra args for info

    def execute(self, args: argparse.Namespace):
        from zotero_cli.core.config import get_config, get_config_path

        config = get_config(args.config)

        print("--- Zotero CLI Info ---")
        print(f"Config Path: {get_config_path() or 'None (using defaults/env)'}")
        print(f"Library ID:  {config.library_id}")
        print(f"Library Type: {config.library_type}")
        print(f"Zotero API Key: {'********' if config.api_key else 'NOT SET'}")
        if config.openai_api_key:
            print("OpenAI API Key: ********")
        if config.gemini_api_key:
            print("Gemini API Key: ********")
        if config.target_group_url:
            print(f"Group URL:   {config.target_group_url}")


@CommandRegistry.register
class SystemCommand(BaseCommand):
    name = "system"
    help = "System maintenance & information"

    def register_args(self, parser: argparse.ArgumentParser):
        sub = parser.add_subparsers(dest="verb", required=True)

        # Info
        sub.add_parser(
            "info",
            help="Display environment and configuration",
            description="Displays the current configuration, environment variables, and connection status of your zotero-cli installation.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Verifying which Zotero group is active
Problem: I'm not sure if my commands are currently targeting my personal library or my research group's library.
Action:  zotero-cli system info
Result:  The CLI displays the "Active Library ID" and the "Library Type" (User/Group).

Cognitive Safeguards
--------------------
• Common Failure Modes: Running the command before initializing the CLI with init.
• Safety Tips: Use this command to confirm your storage_path is set before running bulk fetches.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/system_info.md
""",
        )

        # Groups
        sub.add_parser(
            "groups",
            help="List user groups and IDs",
            description="Lists all Zotero groups that your account belongs to, displaying their names, unique numeric IDs, and your access permissions.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Scenario-Based Examples (Cognitive Anchors)
-------------------------------------------
Scenario: Finding a lab's Group ID for a new project
Problem: I need to move papers into my lab's shared library, but I don't know the numeric ID for the "AI Ethics Lab" group.
Action:  zotero-cli system groups
Result:  The table lists all my groups, and I can see that "AI Ethics Lab" has ID 1234567.

Cognitive Safeguards
--------------------
• Common Failure Modes: Attempting to run the command with an expired or invalid API key.
• Safety Tips: Use this command in combination with system switch to move between different project contexts quickly.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/system_groups.md
""",
        )

        # Backup
        backup_p = sub.add_parser("backup", help="Create a full system backup (.zaf)")
        backup_p.add_argument("--output", required=True, help="Output file path (e.g., backup.zaf)")

        # Restore (Placeholder for now, implemented logic pending)
        restore_p = sub.add_parser("restore", help="Restore from a .zaf backup")
        restore_p.add_argument("--file", required=True, help="Input .zaf file")
        restore_p.add_argument("--dry-run", action="store_true", help="Simulate restore")

        # Normalize CSV
        norm_p = sub.add_parser(
            "normalize", help="Convert external CSV (IEEE, Springer) to Canonical format"
        )
        norm_p.add_argument("file", help="Input CSV file")
        norm_p.add_argument("--output", required=True, help="Output Canonical CSV path")

        # Switch Context
        switch_p = sub.add_parser("switch", help="Switch active group context")
        switch_p.add_argument("query", help="Group ID or Name (partial match)")

        # Jobs (Issue #76 consolidation)
        jobs_p = sub.add_parser("jobs", help="Manage background system jobs")
        jobs_sub = jobs_p.add_subparsers(dest="jobs_verb", required=True)

        # jobs list
        list_p = jobs_sub.add_parser("list", help="List all background jobs")
        list_p.add_argument("--type", help="Filter by task type")
        list_p.add_argument("--limit", type=int, default=50, help="Max jobs to show")

        # jobs retry
        retry_p = jobs_sub.add_parser("retry", help="Retry a failed job")
        retry_p.add_argument("id", type=int, help="Job ID")

        # jobs run (Migration from find-pdf worker)
        run_p = jobs_sub.add_parser("run", help="Run background worker to process jobs")
        run_p.add_argument(
            "--type", default="fetch_pdf", help="Filter by task type (Default: fetch_pdf)"
        )
        run_p.add_argument("--count", type=int, help="Number of jobs to process")
        run_p.add_argument("--watch", action="store_true", help="Live progress monitor")

    def execute(self, args: argparse.Namespace):
        if args.verb == "info":
            InfoCommand().execute(args)
        elif args.verb == "groups":
            self._handle_groups(args)
        elif args.verb == "backup":
            self._handle_backup(args)
        elif args.verb == "restore":
            print("Restore functionality is pending implementation.")
        elif args.verb == "normalize":
            self._handle_normalize(args)
        elif args.verb == "switch":
            self._handle_switch(args)
        elif args.verb == "jobs":
            self._handle_jobs(args)

    def _handle_groups(self, args):
        from zotero_cli.core.config import get_config
        from zotero_cli.infra.factory import GatewayFactory

        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        config = get_config()
        if not config.user_id:
            console.print(
                "[red]Error: ZOTERO_USER_ID not configured. Cannot fetch user groups.[/red]"
            )
            return

        groups = gateway.get_user_groups(config.user_id)
        table = Table(title="Zotero Groups")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("URL")
        for g in groups:
            gid = str(g.get("id", "N/A"))
            # Zotero API v3 structure for /users/{id}/groups:
            # [ { "id": 123, "data": { "name": "Group Name", ... }, ... }, ... ]
            name = g.get("data", {}).get("name", "N/A")
            url = f"https://www.zotero.org/groups/{gid}"
            table.add_row(gid, name, url)
        console.print(table)

    def _handle_jobs(self, args):
        from rich.table import Table

        from zotero_cli.infra.factory import GatewayFactory

        job_service = GatewayFactory.get_job_queue_service()

        if args.jobs_verb == "list":
            jobs = job_service.repo.list_jobs(task_type=args.type, limit=args.limit)
            if not jobs:
                print("No jobs found.")
                return

            table = Table(title="Background System Jobs")
            table.add_column("ID", justify="right", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Item Key", style="green")
            table.add_column("Status")
            table.add_column("Attempts", justify="right")
            table.add_column("Next Retry", style="dim")
            table.add_column("Error", style="red", overflow="fold")

            for j in jobs:
                status_color = {
                    "PENDING": "white",
                    "PROCESSING": "blue",
                    "COMPLETED": "green",
                    "FAILED": "red",
                    "RETRY": "yellow",
                }.get(j.status, "white")

                table.add_row(
                    str(j.id),
                    j.task_type,
                    j.item_key,
                    f"[{status_color}]{j.status}[/]",
                    str(j.attempts),
                    j.next_retry_at or "-",
                    j.last_error or "",
                )
            console.print(table)

        elif args.jobs_verb == "retry":
            job = job_service.repo.get_job(args.id)
            if not job:
                print(f"Error: Job {args.id} not found.")
                return

            job.status = "PENDING"
            job.attempts = 0
            job.next_retry_at = None
            if job_service.repo.update_job(job):
                print(f"[green]Job {args.id} reset to PENDING.[/green]")
            else:
                print(f"[red]Failed to update job {args.id}.[/red]")

        elif args.jobs_verb == "run":
            import asyncio

            worker_service: Any = None
            if args.type == "fetch_pdf":
                worker_service = GatewayFactory.get_pdf_finder_service()
            elif args.type.startswith("discover"):
                worker_service = GatewayFactory.get_snowball_worker()
            else:
                print(f"Error: Unsupported task type '{args.type}' for direct worker.")
                return

            if args.watch:
                self._watch_jobs(job_service, args.type)
            else:
                console.print(f"[bold]Starting worker for task type '{args.type}'...[/bold]")
                asyncio.run(worker_service.process_jobs(count=args.count))
                console.print("[bold green]Done.[/bold green]")

    def _watch_jobs(self, job_service, task_type):
        from rich.live import Live
        from rich.table import Table

        def generate_table():
            jobs = job_service.repo.list_jobs(task_type=task_type, limit=20)
            table = Table(title=f"Live Jobs Monitor: {task_type}")
            table.add_column("ID", justify="right")
            table.add_column("Key")
            table.add_column("Status")
            table.add_column("Attempts")
            table.add_column("Error")

            for j in jobs:
                status_color = {
                    "PENDING": "white",
                    "PROCESSING": "blue",
                    "COMPLETED": "green",
                    "FAILED": "red",
                    "RETRY": "yellow",
                }.get(j.status, "white")
                table.add_row(
                    str(j.id),
                    j.item_key,
                    f"[{status_color}]{j.status}[/]",
                    str(j.attempts),
                    j.last_error or "",
                )
            return table

        with Live(generate_table(), refresh_per_second=1) as live:
            while True:
                live.update(generate_table())
                # Check if any active jobs remain
                jobs = job_service.repo.list_jobs(task_type=task_type, limit=100)
                active = [j for j in jobs if j.status in ("PENDING", "PROCESSING", "RETRY")]
                if not active:
                    break

                # Run worker for 1 job
                svc: Any = None
                if task_type == "fetch_pdf":
                    svc = GatewayFactory.get_pdf_finder_service()
                else:
                    svc = GatewayFactory.get_snowball_worker()

                asyncio.run(svc.process_jobs(count=1))
                time.sleep(0.5)

    def _handle_switch(self, args):
        from rich.prompt import Confirm

        from zotero_cli.core.config import ConfigManager, get_config
        from zotero_cli.infra.factory import GatewayFactory

        config = get_config()
        if not config.user_id:
            print("Error: ZOTERO_USER_ID not configured. Cannot fetch user groups.")
            return

        gateway = GatewayFactory.get_zotero_gateway(force_user=True)
        groups = gateway.get_user_groups(config.user_id)

        query = args.query.lower()
        matches = []

        for g in groups:
            gid = str(g.get("id"))
            name = g.get("data", {}).get("name", "").lower()
            if query == gid or query in name:
                matches.append(g)

        if not matches:
            print(f"No groups found matching '{args.query}'.")
            return

        if len(matches) > 1:
            print(f"Multiple groups found matching '{args.query}':")
            for g in matches:
                print(f" - {g.get('data', {}).get('name')} ({g.get('id')})")
            print("Please be more specific.")
            return

        target = matches[0]
        target_name = target.get("data", {}).get("name")
        target_id = str(target.get("id"))

        if Confirm.ask(f"Switch context to group '{target_name}' ({target_id})?"):
            try:
                manager = ConfigManager()
                manager.save_group_context(target_id)
                print(f"[green]Switched context to group: {target_name} ({target_id})[/green]")
            except Exception as e:
                print(f"[red]Failed to save configuration: {e}[/red]")

    def _handle_normalize(self, args):
        ext = os.path.splitext(args.file)[1].lower()
        strategy: Any = None
        gateway: Any = None

        if ext == ".bib":
            gateway = BibtexLibGateway()
            strategy = BibtexImportStrategy(gateway)
        elif ext == ".ris":
            gateway = RisLibGateway()
            strategy = RisImportStrategy(gateway)
        elif ext == ".csv":
            # 1. Detect CSV Type
            with open(args.file, "r", encoding="utf-8") as f:
                header = f.readline().lower()
                if "item title" in header:
                    gateway = SpringerCsvLibGateway()
                    strategy = SpringerCsvImportStrategy(gateway)
                elif "document title" in header:
                    gateway = IeeeCsvLibGateway()
                    strategy = IeeeCsvImportStrategy(gateway)
                elif "title" in header and "doi" in header:
                    gateway = CanonicalCsvLibGateway()
                    strategy = CanonicalCsvImportStrategy(gateway)
                else:
                    print("Error: Unknown CSV format for normalization.")
                    return
        else:
            print(f"Error: Unsupported file extension {ext}")
            return

        print(f"Parsing {args.file}...")
        papers = list(strategy.fetch_papers(args.file))

        # 2. Write to Canonical
        canon_gw = CanonicalCsvLibGateway()
        canon_gw.write_file(iter(papers), args.output)
        print(f"Normalization complete. Saved {len(papers)} items to {args.output}")

    def _handle_backup(self, args):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
        service = BackupService(gateway)

        print(f"Starting System Backup to {args.output}...")
        try:
            service.backup_system(args.output)
            print(f"Backup complete: {args.output}")
        except Exception as e:
            print(f"Backup failed: {e}", file=sys.stderr)
