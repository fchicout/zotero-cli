from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.exceptions import Unavailable
from zotero_cli.core.services.diagnostics_service import DiagnosticsService


@pytest.fixture
def mock_gateway():
    gateway = MagicMock()
    gateway.original_db_path = None  # online, unless a test says otherwise
    return gateway


@pytest.fixture
def mock_aggregator():
    agg = MagicMock()
    return agg


@pytest.fixture
def base_config():
    return ZoteroConfig(api_key="key", library_id="123")


def make_service(mock_gateway, mock_aggregator, config, llm_provider=None, embedding_provider=None):
    return DiagnosticsService(
        mock_gateway,
        mock_aggregator,
        llm_provider,
        embedding_provider or MagicMock(),
        config,
    )


def result_for(results, name):
    return next(r for r in results if r.name == name)


def test_zotero_connected(mock_gateway, mock_aggregator, base_config):
    mock_gateway.verify_credentials.return_value = True
    service = make_service(mock_gateway, mock_aggregator, base_config)
    result = result_for(service.run_checks(), "Zotero API")
    assert result.status == "CONNECTED"


def test_zotero_failed_credentials(mock_gateway, mock_aggregator, base_config):
    mock_gateway.verify_credentials.return_value = False
    service = make_service(mock_gateway, mock_aggregator, base_config)
    result = result_for(service.run_checks(), "Zotero API")
    assert result.status == "FAILED"


def test_zotero_raises_is_failed(mock_gateway, mock_aggregator, base_config):
    mock_gateway.verify_credentials.side_effect = RuntimeError("network down")
    service = make_service(mock_gateway, mock_aggregator, base_config)
    result = result_for(service.run_checks(), "Zotero API")
    assert result.status == "FAILED"
    assert "network down" in result.details


def test_semantic_scholar_not_configured(mock_gateway, mock_aggregator, base_config):
    assert base_config.semantic_scholar_api_key is None
    service = make_service(mock_gateway, mock_aggregator, base_config)
    result = result_for(service.run_checks(), "Semantic Scholar")
    assert result.status == "NOT_CONFIGURED"
    mock_aggregator.semantic_scholar.get_paper_metadata.assert_not_called()


def test_semantic_scholar_connected(mock_gateway, mock_aggregator):
    config = ZoteroConfig(api_key="k", library_id="1", semantic_scholar_api_key="ss-key")
    mock_aggregator.semantic_scholar.get_paper_metadata.return_value = MagicMock()
    service = make_service(mock_gateway, mock_aggregator, config)
    result = result_for(service.run_checks(), "Semantic Scholar")
    assert result.status == "CONNECTED"


def test_semantic_scholar_failed_none_response(mock_gateway, mock_aggregator):
    config = ZoteroConfig(api_key="k", library_id="1", semantic_scholar_api_key="ss-key")
    mock_aggregator.semantic_scholar.get_paper_metadata.return_value = None
    service = make_service(mock_gateway, mock_aggregator, config)
    result = result_for(service.run_checks(), "Semantic Scholar")
    assert result.status == "FAILED"


def test_unpaywall_not_configured(mock_gateway, mock_aggregator, base_config):
    service = make_service(mock_gateway, mock_aggregator, base_config)
    result = result_for(service.run_checks(), "Unpaywall")
    assert result.status == "NOT_CONFIGURED"


def test_pubmed_not_configured(mock_gateway, mock_aggregator, base_config):
    service = make_service(mock_gateway, mock_aggregator, base_config)
    result = result_for(service.run_checks(), "PubMed/NCBI")
    assert result.status == "NOT_CONFIGURED"


def test_zotero_rejected_key_says_what_to_do(mock_gateway, mock_aggregator, base_config):
    mock_gateway.verify_credentials.return_value = False
    result = result_for(
        make_service(mock_gateway, mock_aggregator, base_config).run_checks(), "Zotero API"
    )
    assert "zotero.org/settings/keys" in result.details
    assert "zotero-cli init" in result.details


def test_zotero_unavailable_is_not_reported_as_a_bad_key(
    mock_gateway, mock_aggregator, base_config
):
    mock_gateway.verify_credentials.side_effect = Unavailable("Zotero API unreachable (timed out)")
    result = result_for(
        make_service(mock_gateway, mock_aggregator, base_config).run_checks(), "Zotero API"
    )
    assert result.status == "FAILED"
    assert "unreachable" in result.details
    assert "key" not in result.details


def test_offline_reports_the_local_database(mock_gateway, mock_aggregator, base_config):
    """--offline doesn't touch the Web API, so don't claim it was verified (Issue #382)."""
    mock_gateway.original_db_path = "/home/u/Zotero/zotero.sqlite"
    mock_gateway.count_items.return_value = 42
    results = make_service(mock_gateway, mock_aggregator, base_config).run_checks()
    names = {r.name for r in results}
    assert "Zotero API" not in names
    row = result_for(results, "Local database")
    assert row.status == "FOUND"
    assert "zotero.sqlite" in row.details and "42 items" in row.details
    mock_gateway.verify_credentials.assert_not_called()


def test_offline_unreadable_database_is_failed(mock_gateway, mock_aggregator, base_config):
    mock_gateway.original_db_path = "/nope/zotero.sqlite"
    mock_gateway.count_items.side_effect = RuntimeError("unable to open database file")
    row = result_for(
        make_service(mock_gateway, mock_aggregator, base_config).run_checks(), "Local database"
    )
    assert row.status == "FAILED"
    assert "unable to open" in row.details


def test_rag_rows_absent_when_not_configured(mock_gateway, mock_aggregator, base_config):
    """Default config (provider 'auto', no model): no FAILED RAG rows on a plain install (#408)."""
    names = {r.name for r in make_service(mock_gateway, mock_aggregator, base_config).run_checks()}
    assert "LLM Provider" not in names
    assert "Embedding Provider" not in names


def test_rag_configured_is_reported_without_calling_providers(mock_gateway, mock_aggregator):
    """No model load, download or API call (Issue #382)."""
    config = ZoteroConfig(
        api_key="k",
        library_id="1",
        embedding_provider="openai",
        generative_provider="gemini",
        generative_model="gemini-pro",
    )
    llm, embedder = MagicMock(), MagicMock()
    with patch("zotero_cli.core.services.diagnostics_service._importable", return_value=True):
        service = DiagnosticsService(mock_gateway, mock_aggregator, llm, embedder, config)
        results = service.run_checks()
    emb = result_for(results, "Embedding Provider")
    gen = result_for(results, "LLM Provider")
    assert emb.status == gen.status == "CONFIGURED"
    assert "gemini-pro" in gen.details
    llm.generate.assert_not_called()
    embedder.embed_text.assert_not_called()


def test_rag_configured_without_the_extra_says_how_to_install(mock_gateway, mock_aggregator):
    config = ZoteroConfig(api_key="k", library_id="1", embedding_provider="local")
    with patch("zotero_cli.core.services.diagnostics_service._importable", return_value=False):
        row = result_for(
            make_service(mock_gateway, mock_aggregator, config).run_checks(), "Embedding Provider"
        )
    assert row.status == "FAILED"
    assert "zotero-command-line[rag]" in row.details


def test_run_checks_default_rows(mock_gateway, mock_aggregator, base_config):
    service = make_service(mock_gateway, mock_aggregator, base_config)
    results = service.run_checks()
    names = {r.name for r in results}
    assert names == {"Zotero API", "Semantic Scholar", "Unpaywall", "PubMed/NCBI"}


def test_unconfigured_library_is_a_required_not_configured_row(mock_aggregator, base_config):
    """Issue #376: `system check` runs before setup and says what's missing."""
    service = DiagnosticsService(
        None,
        mock_aggregator,
        None,
        None,
        base_config,
        "No Zotero API key is set. Run `zotero-cli init`",
    )
    row = result_for(service.run_checks(), "Zotero API")
    assert row.status == "NOT_CONFIGURED"
    assert row.required is True
    assert "zotero-cli init" in row.details
