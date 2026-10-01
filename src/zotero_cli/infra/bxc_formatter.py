"""Formatted bibliographies through bxc (Issue #534)."""

from zotero_cli.core.exceptions import UsageError
from zotero_cli.core.interfaces import BibliographyFormatter

RENDERINGS = ("plain", "markdown", "html")
DEFAULT_STYLE = "apa"


class BxcBibliographyFormatter(BibliographyFormatter):
    """CSL formatting by bxc, which bundles the common styles.

    `offline` stops bxc from fetching a style it doesn't bundle; the cache is
    never written, so formatting leaves nothing behind on the user's disk.
    """

    def __init__(self, offline: bool = False):
        self.offline = offline

    def format(self, bibtex: str, style: str, render: str = "plain") -> str:
        import bxc

        if render not in RENDERINGS:
            raise UsageError(f"Unknown rendering '{render}'. Use one of: {', '.join(RENDERINGS)}.")
        try:
            return bxc.format_bibtex(
                bibtex, style, output_format=render, cache=False, offline=self.offline
            )
        except bxc.StyleNotFoundError as exc:
            raise UsageError(self._style_message(style, str(exc))) from exc

    @staticmethod
    def _style_message(style: str, detail: str) -> str:
        import difflib

        import bxc
        from bxc.cache import offline_mode

        # Only the bundled index: a typo must not trigger a download.
        with offline_mode(True):
            names = [entry["name"] for entry in bxc.search_styles("")]
        close = difflib.get_close_matches(style, names, n=5, cutoff=0.6)
        close += [n for n in names if style in n and n not in close][: 5 - len(close)]
        if not close:
            return detail
        return f"Unknown citation style '{style}'. Close matches: {', '.join(close)}."
