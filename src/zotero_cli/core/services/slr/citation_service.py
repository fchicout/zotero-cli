import re

from zotero_cli.core.zotero_item import ZoteroItem


class CitationService:
    """
    Resolves stable citation keys for Zotero items.
    Priority:
    1. Better BibTeX 'Citation Key' in 'extra' field.
    2. Better BibTeX 'citationKey' in raw JSON metadata.
    3. Generated fallback: FirstAuthorYear (e.g. Chicout2026).
    """

    def resolve_citation_key(self, item: ZoteroItem) -> str:
        # 1. Check 'extra' field for 'Citation Key: KEY'
        if item.extra:
            match = re.search(r"citation key:\s*(\S+)", item.extra, re.I)
            if match:
                return match.group(1)

        # 2. Fallback: Generate from Authors and Year
        author = "Unknown"
        for c in item.creators:
            if c.get("creatorType") == "author":
                author = c.get("lastName") or c.get("name") or "Unknown"
                break

        # Clean author name (remove spaces/special chars)
        author = re.sub(r"\W+", "", author)

        year = item.date or ""
        year_match = re.search(r"\d{4}", year)
        year_str = year_match.group(0) if year_match else "n.d."

        return f"{author}{year_str}"
