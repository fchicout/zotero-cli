from unittest.mock import MagicMock

import pytest

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.services.diagnostics_service import DiagnosticsService


@pytest.fixture
def mock_gateway():
    return MagicMock()


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


def test_llm_provider_not_configured(mock_gateway, mock_aggregator, base_config):
    service = make_service(mock_gateway, mock_aggregator, base_config, llm_provider=None)
    result = result_for(service.run_checks(), "LLM Provider")
    assert result.status == "NOT_CONFIGURED"


def test_llm_provider_connected(mock_gateway, mock_aggregator, base_config):
    llm = MagicMock()
    llm.generate.return_value = "pong"
    service = make_service(mock_gateway, mock_aggregator, base_config, llm_provider=llm)
    result = result_for(service.run_checks(), "LLM Provider")
    assert result.status == "CONNECTED"


def test_llm_provider_raises_is_failed(mock_gateway, mock_aggregator, base_config):
    llm = MagicMock()
    llm.generate.side_effect = RuntimeError("bad key")
    service = make_service(mock_gateway, mock_aggregator, base_config, llm_provider=llm)
    result = result_for(service.run_checks(), "LLM Provider")
    assert result.status == "FAILED"


def test_embedding_provider_connected(mock_gateway, mock_aggregator, base_config):
    embedder = MagicMock()
    embedder.embed_text.return_value = [0.1, 0.2]
    service = make_service(mock_gateway, mock_aggregator, base_config, embedding_provider=embedder)
    result = result_for(service.run_checks(), "Embedding Provider")
    assert result.status == "CONNECTED"


def test_embedding_provider_raises_is_failed(mock_gateway, mock_aggregator, base_config):
    embedder = MagicMock()
    embedder.embed_text.side_effect = RuntimeError("no local model")
    service = make_service(mock_gateway, mock_aggregator, base_config, embedding_provider=embedder)
    result = result_for(service.run_checks(), "Embedding Provider")
    assert result.status == "FAILED"


def test_run_checks_returns_all_six(mock_gateway, mock_aggregator, base_config):
    service = make_service(mock_gateway, mock_aggregator, base_config)
    results = service.run_checks()
    names = {r.name for r in results}
    assert names == {
        "Zotero API",
        "Semantic Scholar",
        "Unpaywall",
        "PubMed/NCBI",
        "LLM Provider",
        "Embedding Provider",
    }
