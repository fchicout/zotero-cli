from typing import Optional


def user_agent(contact_email: Optional[str] = None) -> str:
    """The User-Agent for every outgoing request. It names the program and
    version honestly (Issue #407: never a browser's). "Polite pool"
    providers (CrossRef, OpenAlex) ask for a contact address; it's the
    user's own configured email (`unpaywall_email`), never a built-in one,
    so one user's traffic is never attributed to someone else."""
    from zotero_cli import __version__

    agent = f"zotero-cli/{__version__} (+https://github.com/fchicout/zotero-cli"
    return f"{agent}; mailto:{contact_email})" if contact_email else f"{agent})"
