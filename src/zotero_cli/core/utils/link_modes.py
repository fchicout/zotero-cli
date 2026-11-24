"""Zotero attachment link modes (Issue #655)."""

# Attachments whose file Zotero stores itself, served by the Web API at items/<key>/file:
# a file added by the user, a page or file downloaded from a URL (a web snapshot, or a PDF
# fetched by the Zotero Connector), and an image pasted into a note.
STORED_LINK_MODES = ("imported_file", "imported_url", "embedded_image")
