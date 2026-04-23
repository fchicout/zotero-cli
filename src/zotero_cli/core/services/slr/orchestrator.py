from typing import Dict, List, Optional
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.utils.sdb_parser import parse_sdb_note
from zotero_cli.core.zotero_item import ZoteroItem

class SLROrchestrator:
    """
    Central service for SLR protocol enforcement, hierarchy management,
    and state-to-folder mapping.
    """

    # The canonical definition of our SLR 4-Step Process
    PHASE_FLOW = [
        {"id": "title_abstract", "folder": "1-title_abstract", "label": "1-T&A"},
        {"id": "full_text", "folder": "2-fulltext", "label": "2-FT"},
        {"id": "quality_assessment", "folder": "3-quality_assessment", "label": "3-QA"},
        {"id": "data_extraction", "folder": "4-data_extraction", "label": "4-DE"}
    ]

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def ensure_slr_hierarchy(self, parent_key: str, all_cols: Optional[List[dict]] = None) -> Dict[str, str]:
        """
        Verifies and silently creates the 4-phase subfolders under a source collection.
        Returns a mapping of folder_name -> folder_key.
        """
        if all_cols is None:
            all_cols = self.gateway.get_all_collections()

        existing_subfolders = {
            c["data"]["name"]: c["key"] 
            for c in all_cols 
            if c["data"].get("parentCollection") == parent_key
        }
        
        phase_map = {}
        for phase_cfg in self.PHASE_FLOW:
            name = phase_cfg["folder"]
            if name in existing_subfolders:
                phase_map[name] = existing_subfolders[name]
            else:
                # Create missing folder
                new_key = self.gateway.create_collection(name, parent_key=parent_key)
                if new_key:
                    phase_map[name] = new_key
        return phase_map

    def get_tree_keys(self, root_key: str, all_cols: Optional[List[dict]] = None) -> List[str]:
        """
        Returns a list of all keys belonging to a specific SLR tree (root + phase folders).
        Used for exclusive membership enforcement.
        """
        phase_map = self.ensure_slr_hierarchy(root_key, all_cols)
        keys = [root_key]
        keys.extend(phase_map.values())
        return keys

    def get_all_papers_in_tree(self, root_key: str) -> List[ZoteroItem]:
        """
        Collects every unique top-level paper existing in the root or phase folders.
        """
        tree_keys = self.get_tree_keys(root_key)
        unique_papers = {}
        
        for key in tree_keys:
            items = self.gateway.get_items_in_collection(key, top_only=True)
            for item in items:
                if item.item_type not in ["attachment", "note"]:
                    unique_papers[item.key] = item
                    
        return list(unique_papers.values())

    def resolve_target_phase(self, item_key: str) -> Optional[str]:
        """
        Determines the highest phase an item reached by parsing its child SDB notes.
        Returns the phase_id (e.g. 'full_text') or None if no positive decisions.
        """
        children = self.gateway.get_item_children(item_key)
        highest_phase_id = None
        
        # Priority mapping (Higher index = higher phase)
        phase_order = [p["id"] for p in self.PHASE_FLOW]
        highest_index = -1

        for child in children:
            if child.get("data", {}).get("itemType") == "note":
                parsed = parse_sdb_note(child.get("data", {}).get("note", ""))
                if parsed:
                    phase_id = parsed.get("phase")
                    decision = str(parsed.get("decision", "")).lower()
                    
                    if decision in ["accepted", "approved", "included"]:
                        if phase_id in phase_order:
                            idx = phase_order.index(phase_id)
                            if idx > highest_index:
                                highest_index = idx
                                highest_phase_id = phase_id
                                
        return highest_phase_id

    def get_folder_key_for_phase(self, root_key: str, phase_id: Optional[str]) -> str:
        """
        Maps a phase_id to its actual Zotero folder key within the tree.
        If phase_id is None, returns the root_key.
        """
        if not phase_id:
            return root_key
            
        phase_map = self.ensure_slr_hierarchy(root_key)
        
        # Find folder name for the ID
        target_folder_name = next((p["folder"] for p in self.PHASE_FLOW if p["id"] == phase_id), None)
        
        return phase_map.get(target_folder_name, root_key)
