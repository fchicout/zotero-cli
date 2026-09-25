"""Issue #407: every outgoing request names zotero-cli honestly. The code
used to send rotating browser User-Agents, resend a rejected request under
another identity, and hard-code Firefox strings in three places."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.utils import url_safety
from zotero_cli.core.utils.user_agent import user_agent

SRC = Path(__file__).resolve().parents[3] / "src" / "zotero_cli"


def test_no_browser_user_agent_anywhere_in_src():
    offenders = [
        f"{p.relative_to(SRC)}:{n}"
        for p in SRC.rglob("*.py")
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "Mozilla/5.0" in line
    ]
    assert offenders == []


def test_identity_rotation_is_gone():
    assert not (SRC / "core" / "services" / "identity_manager.py").exists()


def _capture_safe_get_headers(**kwargs) -> dict:
    session = MagicMock()
    response = MagicMock(is_redirect=False, is_permanent_redirect=False)
    session.request.return_value = response
    with (
        patch.object(url_safety, "public_only_session", return_value=session),
        patch.object(url_safety, "validate_public_url"),
    ):
        url_safety.safe_get("https://example.org/paper.pdf", **kwargs)
    return dict(session.request.call_args.kwargs["headers"])


def test_safe_get_sends_the_zotero_cli_user_agent():
    headers = _capture_safe_get_headers()
    assert headers["User-Agent"] == user_agent()
    assert headers["User-Agent"].startswith("zotero-cli/")


def test_safe_get_keeps_other_headers_and_an_explicit_user_agent():
    headers = _capture_safe_get_headers(headers={"Referer": "https://example.org/"})
    assert headers["Referer"] == "https://example.org/"
    assert headers["User-Agent"].startswith("zotero-cli/")

    explicit = _capture_safe_get_headers(headers={"user-agent": "zotero-cli/test"})
    assert explicit == {"user-agent": "zotero-cli/test"}


def test_network_gateway_carries_the_users_contact_address():
    from zotero_cli.infra.resolver_factory import ResolverFactory

    gateway = ResolverFactory.get_network_gateway(ZoteroConfig(unpaywall_email="me@example.org"))

    assert gateway.user_agent == user_agent("me@example.org")
    assert gateway.user_agent.endswith("; mailto:me@example.org)")
