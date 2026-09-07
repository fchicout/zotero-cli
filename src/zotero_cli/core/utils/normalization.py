import re
import unicodedata

# Issue #242: loose but real structural check for a DOI shape
# (registrant prefix "10.NNNN" + "/" + a non-empty suffix) - used to
# reject obviously-garbage values (empty, whitespace, missing the "10."
# prefix) before they're interpolated into an external API request URL.
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")


def is_valid_doi(doi: str) -> bool:
    """Returns True if `doi` has a plausible DOI shape. Not a full DOI
    grammar validator - just enough to catch garbage/malformed values
    before they're used to build a request URL (defense-in-depth;
    callers should still URL-quote the value, since a technically
    DOI-shaped suffix can still legally contain characters like `?`/`#`
    that would otherwise inject into the URL)."""
    return bool(doi) and bool(_DOI_PATTERN.match(doi))


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
