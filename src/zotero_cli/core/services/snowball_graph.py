import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from zotero_cli.core.interfaces import SnowballGraphService as ISnowballGraphService

logger = logging.getLogger(__name__)


class SnowballGraphService(ISnowballGraphService):
    """
    Manages the discovery graph for snowballing (citation tracking).
    Provides relevance ranking based on graph topology.
    """

    STATUS_PENDING = "PENDING"
    STATUS_ACCEPTED = "ACCEPTED"
    STATUS_REJECTED = "REJECTED"

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.graph = nx.DiGraph()
        self.load_graph()

    def add_candidate(
        self,
        paper_metadata: Dict[str, Any],
        parent_doi: Optional[str] = None,
        direction: str = "forward",
        generation: int = 1,
    ):
        """
        Adds a candidate paper to the graph.
        """
        doi = paper_metadata.get("doi")
        if not doi:
            logger.warning("Paper metadata missing DOI. Cannot add to graph.")
            return

        # Add or update node
        if doi not in self.graph:
            self.graph.add_node(
                doi,
                title=paper_metadata.get("title", ""),
                abstract=paper_metadata.get("abstract", ""),
                is_influential=paper_metadata.get("is_influential", False),
                generation=generation,
                status=self.STATUS_PENDING,
            )
        else:
            # If it already exists, we don't overwrite generation/status
            # but we might update metadata if it was a stub
            node = self.graph.nodes[doi]
            if not node.get("title"):
                node["title"] = paper_metadata.get("title", "")
            if not node.get("abstract"):
                node["abstract"] = paper_metadata.get("abstract", "")

        # Add edge if parent exists
        if parent_doi:
            if parent_doi not in self.graph:
                # Add parent as a stub if not present
                self.graph.add_node(
                    parent_doi,
                    title="Stub (Parent)",
                    generation=generation - 1 if generation > 0 else 0,
                    status=self.STATUS_ACCEPTED,
                )

            # Direction:
            # forward: parent -> candidate (parent cites candidate)
            # backward: candidate -> parent (candidate cites parent)
            if direction == "forward":
                self.graph.add_edge(parent_doi, doi, direction="forward")
            else:
                self.graph.add_edge(doi, parent_doi, direction="backward")

    def update_status(self, doi: str, status: str):
        """Transitions node state."""
        if doi in self.graph:
            self.graph.nodes[doi]["status"] = status
            self.save_graph()

    def get_ranked_candidates(self) -> List[Dict[str, Any]]:
        """
        Returns nodes with status=PENDING sorted by In-Degree Centrality
        (incoming edges from nodes with generation=0 or status=ACCEPTED).
        """
        candidates = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("status") == self.STATUS_PENDING:
                # Count citations from 'Seed' or 'Accepted' papers
                # In-degree in a DiGraph: how many other nodes point to me
                # For 'forward' snowballing: seed cites me (edge seed -> me)
                # For 'backward' snowballing: I cite seed (edge me -> seed)
                # The spec mentions "In-Degree Centrality from nodes with generation=0"

                relevance_score = 0
                for predecessor in self.graph.predecessors(node_id):
                    pred_data = self.graph.nodes[predecessor]
                    if (
                        pred_data.get("generation") == 0
                        or pred_data.get("status") == self.STATUS_ACCEPTED
                    ):
                        relevance_score += 1

                # Also consider nodes I cite that are accepted? (Backward)
                for successor in self.graph.successors(node_id):
                    succ_data = self.graph.nodes[successor]
                    if (
                        succ_data.get("generation") == 0
                        or succ_data.get("status") == self.STATUS_ACCEPTED
                    ):
                        # If I cite a seed paper, it adds to my relevance
                        relevance_score += 1

                candidate_info = data.copy()
                candidate_info["doi"] = node_id
                candidate_info["relevance_score"] = relevance_score
                candidates.append(candidate_info)

        # Sort by relevance score descending
        return sorted(candidates, key=lambda x: x["relevance_score"], reverse=True)

    def save_graph(self):
        """Persistence logic."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.graph)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_graph(self):
        """Loads graph from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.graph = nx.node_link_graph(data)
            except Exception as e:
                logger.error(f"Failed to load discovery graph: {e}")
                self.graph = nx.DiGraph()

    def get_stats(self) -> Dict[str, Any]:
        """Returns graph statistics."""
        stats = {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "by_status": {
                self.STATUS_PENDING: 0,
                self.STATUS_ACCEPTED: 0,
                self.STATUS_REJECTED: 0,
                "IMPORTED": 0,
            },
            "by_generation": {},
        }

        for _, data in self.graph.nodes(data=True):
            status = data.get("status", "UNKNOWN")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

            gen = data.get("generation", 0)
            stats["by_generation"][gen] = stats["by_generation"].get(gen, 0) + 1

        return stats

    def to_mermaid(self) -> str:
        """Generates Mermaid graph TD string."""
        lines = ["graph TD"]

        # 1. Define nodes with formatting based on status
        for node_id, data in self.graph.nodes(data=True):
            title = (data.get("title") or node_id)[:40].replace('"', "'")
            status = data.get("status")

            # Mermaid node syntax: ID["Label"]
            # Formatting based on status
            if status == self.STATUS_ACCEPTED:
                lines.append(f'  {node_id}["{title} (ACCEPTED)"]')
                lines.append(f"  style {node_id} fill:#dfd,stroke:#3c3")
            elif status == self.STATUS_REJECTED:
                lines.append(f'  {node_id}["{title} (REJECTED)"]')
                lines.append(f"  style {node_id} fill:#fdd,stroke:#c33")
            elif status == "IMPORTED":
                lines.append(f'  {node_id}["{title} (IMPORTED)"]')
                lines.append(f"  style {node_id} fill:#ddf,stroke:#33c")
            else:
                lines.append(f'  {node_id}["{title}"]')

        # 2. Define edges
        for u, v, data in self.graph.edges(data=True):
            direction = data.get("direction", "forward")
            if direction == "forward":
                lines.append(f"  {u} --> {v}")
            else:
                lines.append(f"  {u} -- cited by --> {v}")

        return "\n".join(lines)
