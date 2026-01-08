from typing import List, Dict, Set, Tuple
from collections import defaultdict
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.zotero_item import ZoteroItem

class CitationGraphService:
    def __init__(self, zotero_gateway: ZoteroGateway, metadata_service: MetadataAggregatorService):
        self.zotero_gateway = zotero_gateway
        self.metadata_service = metadata_service

    def build_graph(self, collection_names: List[str]) -> str:
        doi_to_item_map: Dict[str, ZoteroItem] = {}
        
        # 1. Collect all ZoteroItems with DOIs from specified collections
        for col_name in collection_names:
            col_id = self.zotero_gateway.get_collection_id_by_name(col_name)
            if not col_id:
                print(f"Warning: Collection '{col_name}' not found. Skipping.")
                continue
            
            for item in self.zotero_gateway.get_items_in_collection(col_id):
                if item.doi:
                    doi_to_item_map[item.doi] = item
        
        all_dois_in_collections: Set[str] = set(doi_to_item_map.keys())
        graph_edges: List[Tuple[str, str]] = [] # (citing_doi, cited_doi)

        # 2. Build graph edges by fetching metadata
        for citing_doi, citing_item in doi_to_item_map.items():
            # Use aggregator to get best metadata including references
            enriched_item = self.metadata_service.get_enriched_metadata(citing_doi)
            
            if enriched_item and enriched_item.references:
                for cited_doi in enriched_item.references:
                    # Only add an edge if the cited paper is also in our collected items
                    if cited_doi in all_dois_in_collections:
                        graph_edges.append((citing_doi, cited_doi))

        # 3. Generate DOT string
        dot_string = "digraph CitationGraph {\n"
        dot_string += '  rankdir="LR";\n' # Left-to-right layout
        
        # Add nodes
        for doi, item in doi_to_item_map.items():
            label = item.title if item.title else f"Item {item.key}"
            # Sanitize label for DOT (replace quotes and escape special chars)
            label = label.replace('"', '\"').replace('\n', ' ').strip()
            dot_string += f'  "{doi}" [label="{label}"];\n'

        # Add edges
        for citing, cited in graph_edges:
            dot_string += f'  "{citing}" -> "{cited}";\n'
        
        dot_string += "}\n"
        
        return dot_string