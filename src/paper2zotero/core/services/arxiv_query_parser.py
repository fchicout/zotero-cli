from dataclasses import dataclass
from typing import Optional, List, Dict
import re
import datetime

@dataclass
class ArxivSearchParams:
    query: str
    max_results: int = 100
    sort_by: str = "relevance"
    sort_order: str = "descending"

class ArxivQueryParser:
    def parse(self, query_str: str) -> ArxivSearchParams:
        # Defaults
        params = {
            'max_results': 100,
            'sort_by': 'relevance',
            'sort_order': 'descending'
        }
        
        # Split by ; to identify top-level keys
        # We need to be careful if ; appears in values (unlikely for current DSL except terms)
        # But my test showed splitting by ; works if we handle continuation.
        
        parts = [p.strip() for p in query_str.split(';')]
        parsed_data: Dict[str, str] = {}
        current_key = None
        
        known_keys = {'order', 'size', 'date_range', 'classification', 'include_cross_list', 'terms'}
        
        for part in parts:
            if not part: continue
            
            # Check if part starts with "key:"
            match = re.match(r'^(' + '|'.join(known_keys) + r'):\s*(.*)', part)
            if match:
                current_key = match.group(1)
                value = match.group(2)
                parsed_data[current_key] = value
            else:
                # Append to current key (likely terms)
                if current_key:
                    parsed_data[current_key] += "; " + part
                    
        # Construct ArXiv Query
        arxiv_query_parts = []
        
        # Classification
        if 'classification' in parsed_data:
            if 'Computer Science (cs)' in parsed_data['classification']:
                arxiv_query_parts.append('cat:cs.*')
            # Add other mappings if needed
        
        # Date Range
        if 'date_range' in parsed_data:
            # "from 2020-01-01"
            match = re.search(r'from\s+(\d{4}-\d{2}-\d{2})', parsed_data['date_range'])
            if match:
                start_date = match.group(1).replace('-', '') + "0000"
                # Use a far future date for open ended
                end_date = "209901010000" 
                arxiv_query_parts.append(f"submittedDate:[{start_date} TO {end_date}]")

        # Terms
        if 'terms' in parsed_data:
            raw_terms_str = parsed_data['terms']
            # Split by ; to get the AND groups
            term_groups = [t.strip() for t in raw_terms_str.split(';')]
            
            parsed_groups = []
            for group in term_groups:
                if not group: continue
                
                # Remove leading AND
                clean_group = re.sub(r'^\s*AND\s+', '', group, flags=re.IGNORECASE)
                
                # Check for field=value pattern
                match = re.match(r'^(\w+)=(.*)', clean_group)
                if match:
                    field = match.group(1)
                    value = match.group(2)
                    
                    # Fix quotes in value: replace ' with "
                    value = value.replace("'", '"')
                    
                    # Construct grouped query part
                    parsed_groups.append(f'{field}:({value})')
                else:
                    parsed_groups.append(f'({clean_group})')
            
            if parsed_groups:
                arxiv_query_parts.append(" AND ".join(parsed_groups))
        
        final_query = " AND ".join(arxiv_query_parts)
        
        # Order
        if 'order' in parsed_data:
            order_val = parsed_data['order']
            if '-announced_date_first' in order_val:
                params['sort_by'] = 'submittedDate'
                params['sort_order'] = 'descending'
            elif 'announced_date_first' in order_val:
                params['sort_by'] = 'submittedDate'
                params['sort_order'] = 'ascending'
                
        # Size
        if 'size' in parsed_data:
            try:
                params['max_results'] = int(parsed_data['size'])
            except ValueError:
                pass
                
        return ArxivSearchParams(
            query=final_query,
            max_results=params['max_results'],
            sort_by=params['sort_by'],
            sort_order=params['sort_order']
        )
