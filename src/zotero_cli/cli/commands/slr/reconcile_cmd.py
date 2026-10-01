import argparse

from rich.table import Table

from zotero_cli.cli.flags import add_details_flag
from zotero_cli.core.exceptions import NotFound
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.utils.terminal_safety import safe_markup
from zotero_cli.infra.factory import GatewayFactory

console = Console()


# Placeholder target for a phase folder that doesn't exist yet (preview only).
_MISSING = "missing-folder:"


class ReconcileCommand:
    """
    CLI command to reconcile the physical location of items with their SDB audit state.
    """

    @staticmethod
    def register_args(parser: argparse.ArgumentParser) -> None:
        parser.description = "Synchronizes the physical folder location of papers with their highest verified SLR phase."
        parser.add_argument(
            "--tree", required=True, help="Root collection name or key (e.g. raw_acm)"
        )
        parser.add_argument(
            "--qa-threshold",
            type=float,
            default=2.0,
            help="Minimum total score for QA success (default: 2.0)",
        )
        parser.add_argument(
            "--execute", action="store_true", help="Perform the actual displacement moves"
        )
        add_details_flag(parser, "Show detailed move logs")

    @staticmethod
    def execute(args: argparse.Namespace) -> None:
        from typing import Any, Dict, List

        from zotero_cli.core.zotero_item import ZoteroItem

        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)
        orchestrator = GatewayFactory.get_slr_orchestrator(force_user=force_user)
        coll_service = GatewayFactory.get_collection_service(force_user=force_user)

        # 1. Resolve Tree Root
        root_key = gateway.get_collection_id_by_name(args.tree) or args.tree
        if not gateway.get_collection(root_key):
            raise NotFound(f"Tree root '{args.tree}' not found.")

        with console.status(f"[bold green]Auditing SLR Tree: {safe_markup(args.tree)}..."):
            # 2. Aggregation: Get all papers in tree
            papers: List[ZoteroItem] = orchestrator.get_all_papers_in_tree(root_key)
            tree_keys = set(orchestrator.get_tree_keys(root_key))
            # Read-only until --execute (Issue #367): a missing phase folder
            # is planned by name and created only when the plan is applied.
            phase_map = orchestrator.find_slr_hierarchy(root_key)

            planned_moves: List[Dict[str, Any]] = []

            # 3. Resolve State & Diff for each paper
            for paper in papers:
                target_phase_id = orchestrator.resolve_target_phase(
                    paper.key, default_qa_threshold=args.qa_threshold
                )
                folder_name = orchestrator.phase_folder_name(target_phase_id)
                if folder_name is None:
                    target_folder_key = root_key
                else:
                    target_folder_key = phase_map.get(folder_name) or _MISSING + folder_name

                current_cols = set(paper.collections)

                # Check for "Exclusive Membership" violation:
                # - Paper must be in target_folder_key
                # - Paper must NOT be in any other tree_keys
                other_tree_cols = (current_cols & tree_keys) - {target_folder_key}

                needs_move = (target_folder_key not in current_cols) or (len(other_tree_cols) > 0)

                if needs_move:
                    planned_moves.append(
                        {
                            "paper": paper,
                            "current": list(current_cols & tree_keys),
                            "target_id": target_folder_key,
                            "target_phase": target_phase_id or "Root/Rejected",
                        }
                    )

        if not planned_moves:
            console.print(
                f"[bold green]Tree '{safe_markup(args.tree)}' is perfectly synchronized. No moves needed.[/bold green]"
            )
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
            if m["target_id"].startswith(_MISSING):
                target_name = f"{m['target_id'][len(_MISSING) :]} (created with --execute)"
            elif m["target_id"] != root_key:
                tc = gateway.get_collection(m["target_id"])
                target_name = tc["data"]["name"] if tc else m["target_id"]

            table.add_row(
                f"{safe_markup(p.title[:40])}... ({safe_markup(p.key)})",
                safe_markup(", ".join(curr_names)),
                f"{safe_markup(m['target_phase'])} -> {safe_markup(target_name)}",
            )

        console.print(table)

        if not args.execute:
            console.print("\n[yellow]DRY RUN: Omit --execute to apply these changes.[/yellow]")
            return

        # 5. Execution: create any missing phase folder, then resolve the
        # planned targets to real keys.
        if any(m["target_id"].startswith(_MISSING) for m in planned_moves):
            created = orchestrator.ensure_slr_hierarchy(root_key)
            for m in planned_moves:
                if m["target_id"].startswith(_MISSING):
                    m["target_id"] = created.get(m["target_id"][len(_MISSING) :], root_key)
            tree_keys |= set(created.values())

        # Exclusive Sticky Move
        success_count = 0
        with console.status("[bold blue]Executing displacements...") as status:
            for i, m in enumerate(planned_moves):
                p = m["paper"]
                status.update(f"[bold blue]Moving {i + 1}/{len(planned_moves)}: {p.key}...")

                # We use the coll_service._perform_move directly because we want
                # to clear ALL other tree keys at once (exclusive membership).
                # _perform_move(item, source_id, target_id) clears source_id.
                # But here we want a stronger guarantee.

                # Calculate the exact collection set we want
                other_collections = set(p.collections) - tree_keys
                list(other_collections | {m["target_id"]})

                # Fetch children and perform bulk update (re-using the logic from _perform_move)
                # For simplicity and reliability, we let the existing move_item handle it
                # but we might need a multi-source removal.

                # RECONCILE STRATEGY: Move to target from whatever tree key it was in.
                # If it was in multiple, we loop.
                sources = m["current"] if m["current"] else [None]

                # First move establishes the target and removes ONE source.
                first_src = sources[0]
                if coll_service.move_item(first_src, m["target_id"], p.key):
                    # Remove from remaining tree sources if any
                    for extra_src in sources[1:]:
                        coll_service.move_item(extra_src, m["target_id"], p.key)

                    # Update SDB Note for QA reconciliation
                    # 1. Accepted at QA
                    if m["target_phase"] == "quality_assessment":
                        orchestrator.reconcile_qa_audit(p.key, args.qa_threshold, "accepted")
                    # 2. Rejected at QA (Demoted to FT)
                    elif m["target_phase"] == "full_text":
                        # We only audit if it actually has a QA note to update
                        orchestrator.reconcile_qa_audit(p.key, args.qa_threshold, "rejected")

                    success_count += 1

        console.print(
            f"\n[bold green]RECONCILE COMPLETE:[/bold green] {success_count} items synchronized."
        )
