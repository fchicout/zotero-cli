import re
import unicodedata


def normalize_doi(doi: str) -> str:
    """
    Standardizes DOI to a clean format (no http/https prefix).
    """
    if not doi:
        return ""
    doi = doi.strip().lower()
    # Remove URL prefixes
    doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi)
    # Remove 'doi:' prefix
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi

def normalize_title(title: str) -> str:
    """
    Standardizes titles for fuzzy matching (lowercase, no punctuation, no extra spaces).
    """
    if not title:
        return ""
    # Normalize unicode (accents, etc)
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    # Lowercase and remove punctuation
    title = re.sub(r"[^\w\s]", "", title.lower())
    # Remove extra whitespace
    title = " ".join(title.split())
    return title
