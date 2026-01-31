import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

logger = logging.getLogger(__name__)


class SnowballGraphService:
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
