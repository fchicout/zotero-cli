import re
from dataclasses import dataclass
from typing import Dict, List


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

    _KNOWN_KEYS = (
        "order",
        "size",
        "date_range",
        "classification",
        "include_cross_list",
        "terms",
    )

    def parse(self, query_str: str) -> ArxivSearchParams:
        max_results = 100
        sort_by = "relevance"
        sort_order = "descending"

        sections = self._split_sections(query_str)

        clauses = []
        if "classification" in sections:
            clauses += self._classification_clause(sections["classification"])
        if "date_range" in sections:
            clauses += self._date_range_clause(sections["date_range"])
        if "terms" in sections:
            clauses += self._terms_clause(sections["terms"])
        final_query = " AND ".join(clauses)

        if "order" in sections:
            val = sections["order"]
            if "announced_date_first" in val:
                sort_by = "submittedDate"
                sort_order = "descending"
            elif "announced_date_last" in val:
                sort_by = "submittedDate"
                sort_order = "ascending"

        if "size" in sections:
            try:
                max_results = int(sections["size"])
            except ValueError:
                pass

        return ArxivSearchParams(
            query=final_query,
            max_results=max_results,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    @classmethod
    def _split_sections(cls, query_str: str) -> Dict[str, str]:
        """The `key: value` sections of the DSL; text after a `;` that starts no known
        key continues the previous section (the terms contain `;`)."""
        sections: Dict[str, str] = {}
        current_key = None
        for part in (p.strip() for p in query_str.split(";")):
            if not part:
                continue

            # Check if part starts with "key:"
            match = re.match(r"^(" + "|".join(cls._KNOWN_KEYS) + r"):\s*(.*)", part)
            if match:
                current_key = match.group(1)
                sections[current_key] = match.group(2)
            elif current_key:
                # Append to current key (likely terms)
                sections[current_key] += "; " + part
        return sections

    @staticmethod
    def _classification_clause(value: str) -> List[str]:
        val = value.lower()
        if "computer science" in val or "(cs)" in val:
            return ["cat:cs.*"]
        return []

    @staticmethod
    def _date_range_clause(value: str) -> List[str]:
        match = re.search(r"from\s+(\d{4}-\d{2}-\d{2})", value, re.IGNORECASE)
        if not match:
            return []
        start_date = match.group(1).replace("-", "") + "0000"
        # Use a far future date for open ended
        end_date = "209901010000"
        return [f"submittedDate:[{start_date} TO {end_date}]"]

    @staticmethod
    def _terms_clause(raw_terms_str: str) -> List[str]:
        # Split by ; to get the AND groups
        parsed_groups = []
        for group in (t.strip() for t in raw_terms_str.split(";")):
            if not group:
                continue

            # Remove leading AND
            clean_group = re.sub(r"^\s*AND\s+", "", group, flags=re.IGNORECASE)

            # Check for field=value pattern
            match = re.match(r"^(\w+)=(.*)", clean_group)
            if match:
                field = match.group(1)
                # Replace ' with "
                value = match.group(2).replace("'", '"')

                # Logic: field:value
                if (" " in value or " OR " in value.upper()) and not (
                    value.startswith("(") and value.endswith(")")
                ):
                    value = f"({value})"

                parsed_groups.append(f"{field}:{value}")
            else:
                parsed_groups.append(f"({clean_group.replace(chr(39), chr(34))})")

        return [" AND ".join(parsed_groups)] if parsed_groups else []
