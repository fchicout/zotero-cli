from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json
import re
from datetime import datetime

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem

@dataclass
class PrismaReport:
    collection_name: str
    total_items: int = 0
    screened_items: int = 0
    accepted_items: int = 0
    rejected_items: int = 0
    rejections_by_code: Dict[str, int] = field(default_factory=dict)
    malformed_notes: List[str] = field(default_factory=list) # List of Item Keys

class ReportService:
    """
    Service for generating systematic review reports (PRISMA).
    Parses Standardized Decision Blocks (SDB) from Zotero notes.
    """

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def generate_prisma_report(self, collection_name: str) -> Optional[PrismaReport]:
        col_id = self.gateway.get_collection_id_by_name(collection_name)
        if not col_id:
            return None

        report = PrismaReport(collection_name=collection_name)
        items = self.gateway.get_items_in_collection(col_id)
        
        for item in items:
            report.total_items += 1
            self._process_item_notes(item, report)
            
        return report

    def generate_mermaid_prisma(self, report: PrismaReport) -> str:
        """Generates Mermaid DSL for a PRISMA Flow Diagram."""
        # Simple PRISMA 2020 Flow
        mermaid = [
            "graph TD",
            f"  A[Identification: {report.total_items} items] --> B[Screening: {report.screened_items} items]",
            f"  B --> C{{Decision}}",
            f"  C -- Included --> D[Accepted: {report.accepted_items}]",
            f"  C -- Excluded --> E[Rejected: {report.rejected_items}]"
        ]
        
        # Add rejection breakdown if available
        if report.rejections_by_code:
            for i, (code, count) in enumerate(report.rejections_by_code.items()):
                mermaid.append(f"  E --> E{i}[{code}: {count}]")
                
        return "\n".join(mermaid)

    def render_diagram(self, mermaid_code: str, output_path: str) -> bool:
        """Renders Mermaid code to an image file using mermaid-py library."""
        try:
            import mermaid as mm
            # mermaid-py uses mermaid.ink by default
            chart = mm.Mermaid(mermaid_code)
            # The library typically returns a 'chart' object that can be saved
            # Depending on version, it might be chart.to_svg() or similar.
            # Let's use a safe implementation based on mermaid-py docs
            with open(output_path, "wb") as f:
                f.write(chart.img_bytes)
            return True
        except Exception as e:
            print(f"Error rendering diagram: {e}")
            return False

    def _process_item_notes(self, item: ZoteroItem, report: PrismaReport):
        children = self.gateway.get_item_children(item.key)
        has_valid_note = False
        
        for child in children:
            if child.get('itemType') == 'note' or child.get('data', {}).get('itemType') == 'note':
                # Handle different API response structures
                note_data = child.get('data', child)
                note_content = note_data.get('note', '')
                
                # Extract JSON from <div> if present
                json_str = self._extract_json_from_note(note_content)
                if not json_str:
                    continue
                
                try:
                    data = json.loads(json_str)
                    # Check if it's a screening decision
                    if data.get('action') == 'screening_decision' or 'audit_version' in data:
                        has_valid_note = True
                        decision = data.get('decision', '').lower()
                        
                        if decision in ['accepted', 'include']:
                            report.accepted_items += 1
                        elif decision in ['rejected', 'exclude']:
                            report.rejected_items += 1
                            # Aggregate rejections by code
                            codes = data.get('reason_code', [])
                            if isinstance(codes, str): # Handle legacy single string
                                codes = [codes]
                            elif not codes and 'code' in data: # Handle legacy field name
                                codes = [data['code']]
                                
                            for code in codes:
                                report.rejections_by_code[code] = report.rejections_by_code.get(code, 0) + 1
                        
                        report.screened_items += 1
                        # Only process the latest decision note for stats? 
                        # For PRISMA, usually one decision per stage.
                        break 
                except json.JSONDecodeError:
                    report.malformed_notes.append(item.key)

    def _extract_json_from_note(self, content: str) -> Optional[str]:
        """Extracts JSON string from within <div> tags or raw text."""
        # Simple extraction logic
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return match.group(0)
        return None
