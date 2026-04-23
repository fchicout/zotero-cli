import argparse
import sys
from rich.console import Console
from rich.table import Table

from zotero_cli.infra.factory import GatewayFactory
from zotero_cli.core.services.slr.orchestrator import SLROrchestrator

console = Console()

class ReconcileCommand:
    """
    CLI command to reconcile the physical location of items with their SDB audit state.
    """

    @staticmethod
    def register_args(parser: argparse.ArgumentParser):
        parser.description = "Synchronizes the physical folder location of papers with their highest verified SLR phase."
        parser.add_argument("--tree", required=True, help="Root collection name or key (e.g. raw_acm)")
        parser.add_argument("--execute", action="store_true", help="Perform the actual displacement moves")
        parser.add_argument("--verbose", action="store_true", help="Show detailed move logs")

    @staticmethod
    def execute(args: argparse.Namespace):
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
        orchestrator = SLROrchestrator(gateway)
        coll_service = GatewayFactory.get_collection_service(force_user=force_user)
        
        # 1. Resolve Tree Root
        root_key = gateway.get_collection_id_by_name(args.tree) or args.tree
        if not gateway.get_collection(root_key):
            console.print(f"[bold red]Error:[/bold red] Tree root '{args.tree}' not found.")
            return

        with console.status(f"[bold green]Auditing SLR Tree: {args.tree}..."):
            # 2. Aggregation: Get all papers in tree
            papers = orchestrator.get_all_papers_in_tree(root_key)
            tree_keys = set(orchestrator.get_tree_keys(root_key))
            
            planned_moves = []
            
            # 3. Resolve State & Diff for each paper
            for paper in papers:
                target_phase_id = orchestrator.resolve_target_phase(paper.key)
                target_folder_key = orchestrator.get_folder_key_for_phase(root_key, target_phase_id)
                
                current_cols = set(paper.collections)
                
                # Check for "Exclusive Membership" violation:
                # - Paper must be in target_folder_key
                # - Paper must NOT be in any other tree_keys
                other_tree_cols = (current_cols & tree_keys) - {target_folder_key}
                
                needs_move = (target_folder_key not in current_cols) or (len(other_tree_cols) > 0)
                
                if needs_move:
                    planned_moves.append({
                        "paper": paper,
                        "current": list(current_cols & tree_keys),
                        "target_id": target_folder_key,
                        "target_phase": target_phase_id or "Root/Rejected"
                    })

        if not planned_moves:
            console.print("[bold green]Tree is perfectly synchronized. No moves needed.[/bold green]")
            return

        # 4. Report Plan
        table = Table(title=f"Reconciliation Plan for {args.tree}")
        table.add_column("Paper", style="cyan")
        table.add_column("Current Folder(s)", style="yellow")
        table.add_column("Target Phase/Folder", style="green")

        for m in planned_moves:
            p = m["paper"]
            curr_names = []
            for ckey in m["current"]:
                c = gateway.get_collection(ckey)
                curr_names.append(c["data"]["name"] if c else ckey)
                
            target_name = "Root"
            if m["target_id"] != root_key:
                tc = gateway.get_collection(m["target_id"])
                target_name = tc["data"]["name"] if tc else m["target_id"]

            table.add_row(
                f"{p.title[:40]}... ({p.key})",
                ", ".join(curr_names),
                f"{m['target_phase']} -> {target_name}"
            )

        console.print(table)

        if not args.execute:
            console.print("\n[yellow]DRY RUN: Omit --execute to apply these changes.[/yellow]")
            return

        # 5. Execution: Exclusive Sticky Move
        success_count = 0
        with console.status("[bold blue]Executing displacements...") as status:
            for i, m in enumerate(planned_moves):
                p = m["paper"]
                status.update(f"[bold blue]Moving {i+1}/{len(planned_moves)}: {p.key}...")
                
                # We use the coll_service._perform_move directly because we want 
                # to clear ALL other tree keys at once (exclusive membership).
                # _perform_move(item, source_id, target_id) clears source_id.
                # But here we want a stronger guarantee.
                
                # Calculate the exact collection set we want
                other_collections = set(p.collections) - tree_keys
                final_collections = list(other_collections | {m["target_id"]})
                
                # Fetch children and perform bulk update (re-using the logic from _perform_move)
                # For simplicity and reliability, we let the existing move_item handle it 
                # but we might need a multi-source removal.
                
                # RECONCILE STRATEGY: Move to target from whatever tree key it was in.
                # If it was in multiple, we loop.
                move_success = True
                sources = m["current"] if m["current"] else [None]
                
                # First move establishes the target and removes ONE source.
                first_src = sources[0]
                if coll_service.move_item(first_src, m["target_id"], p.key):
                    # Remove from remaining tree sources if any
                    for extra_src in sources[1:]:
                        coll_service.move_item(extra_src, m["target_id"], p.key)
                    success_count += 1
                else:
                    move_success = False

        console.print(f"\n[bold green]RECONCILE COMPLETE:[/bold green] {success_count} items synchronized.")
