from typing import List, Dict, Any, Optional
import sys
import csv
import json
import io

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem

class LookupService:
    """
    Service responsible for bulk fetching Zotero items and formatting them for reports.
    """

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def lookup_items(
        self, 
        keys: List[str], 
        fields: List[str] = ["key", "arxiv_id", "title", "date", "url"], 
        output_format: str = "table"
    ) -> str:
        """
        Fetches metadata for a list of item keys and returns a formatted string.
        
        Args:
            keys: List of Zotero item keys to fetch.
            fields: List of fields to include in the output.
            output_format: 'table' (Markdown), 'csv', or 'json'.
            
        Returns:
            Formatted string representation of the data.
        """
        results: List[Dict[str, Any]] = []
        
        # Optimization: Zotero API allows fetching multiple items by key comma-separated?
        # The documentation says /items?itemKey=A,B,C is possible.
        # Let's try to batch them in chunks of 50 (safe limit).
        
        chunk_size = 50
        for i in range(0, len(keys), chunk_size):
            chunk_keys = keys[i:i + chunk_size]
            # Since our gateway interface currently only has get_item (singular), 
            # we should technically refactor the gateway to support get_items(keys=[]).
            # But for now, we will iterate. If performance is bad, we refactor Gateway later.
            # Wait, let's be Pythias: efficient. 
            # The Gateway Interface is abstract. We can add get_items_by_keys to it?
            # Or just use get_item loop for now as per MVP. 
            # Given `fetch_details.py` was slow, let's stick to the loop for V1 
            # but assume we might parallelize if needed.
            
            for key in chunk_keys:
                item = self.gateway.get_item(key)
                if item:
                    results.append(self._extract_fields(item, fields))
                else:
                    # Append error placeholder
                    error_row = {f: "N/A" for f in fields}
                    error_row["key"] = key
                    error_row["title"] = "ERROR: Item not found"
                    results.append(error_row)

        return self._format_output(results, fields, output_format)

    def _extract_fields(self, item: ZoteroItem, fields: List[str]) -> Dict[str, Any]:
        """Extracts requested fields from a ZoteroItem."""
        row = {}
        for field in fields:
            if field == "authors":
                val = ", ".join(item.authors) if item.authors else ""
            else:
                val = getattr(item, field, None)
                if val is None:
                    # Fallback to ZoteroItem __dict__ or empty
                    val = "N/A"
            
            # Clean string for table formatting (remove pipes/newlines)
            if isinstance(val, str):
                val = val.replace("|", "-").replace("\n", " ")
            
            row[field] = val
        return row

    def _format_output(self, data: List[Dict[str, Any]], fields: List[str], fmt: str) -> str:
        """Formats the list of dicts into the requested string format."""
        if not data:
            return "No results found."

        if fmt == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)
        
        elif fmt == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
            return output.getvalue()
            
        elif fmt == "table":
            # Markdown Table
            # Header
            header = "| " + " | ".join(fields) + " |"
            separator = "| " + " | ".join(["---"] * len(fields)) + " |"
            rows = []
            for row in data:
                rows.append("| " + " | ".join(str(row.get(f, "")) for f in fields) + " |")
            return f"{header}\n{separator}\n" + "\n".join(rows)
        
        else:
            return "Error: Unknown format."
