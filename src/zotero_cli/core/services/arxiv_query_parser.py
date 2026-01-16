import re
from dataclasses import dataclass
from typing import Dict


@dataclass
class ArxivSearchParams:
    query: str
    max_results: int
    sort_by: str
    sort_order: str

class ArxivQueryParser:
    """
    Parses a DSL string into ArXiv search parameters.
    Example: "order: -announced_date_first; size: 200; terms: ti=Attention"
    """

    def parse(self, query_str: str) -> ArxivSearchParams:
        from typing import Any
        params: Dict[str, Any] = {
            'max_results': 100,
            'sort_by': 'relevance',
            'sort_order': 'descending'
        }

        # Split by ; to identify top-level keys
        parts = [p.strip() for p in query_str.split(';')]
        parsed_data: Dict[str, str] = {}
        current_key = None

        known_keys = {'order', 'size', 'date_range', 'classification', 'include_cross_list', 'terms'}

        for part in parts:
            if not part:
                continue

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
            val = parsed_data['classification'].lower()
            if 'computer science' in val or '(cs)' in val:
                arxiv_query_parts.append('cat:cs.*')

        # Date Range
        if 'date_range' in parsed_data:
            val = parsed_data['date_range']
            match = re.search(r'from\s+(\d{4}-\d{2}-\d{2})', val, re.IGNORECASE)
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
                if not group:
                    continue

                # Remove leading AND
                clean_group = re.sub(r'^\s*AND\s+', '', group, flags=re.IGNORECASE)

                # Check for field=value pattern
                match = re.match(r'^(\w+)=(.*)', clean_group)
                if match:
                    field = match.group(1)
                    value = match.group(2)

                    # Replace ' with "
                    value = value.replace("'", '"')

                    # Logic: field:value
                    parsed_groups.append(f'{field}:{value}')
                else:
                    clean_group_escaped = clean_group.replace("'", '"')
                    parsed_groups.append(f'({clean_group_escaped})')

            if parsed_groups:
                arxiv_query_parts.append(" AND ".join(parsed_groups))

        final_query = " AND ".join(arxiv_query_parts)

        # Order
        if 'order' in parsed_data:
            val = parsed_data['order']
            if 'announced_date_first' in val:
                params['sort_by'] = 'submittedDate'
                params['sort_order'] = 'descending'
            elif 'announced_date_last' in val:
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
