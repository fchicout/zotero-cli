"""GHSA-wv6f-cg7x-pg85: rag models load at pinned commits, and repository
code runs only with the user's explicit consent."""

import re
import sys
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.core.exceptions import ConfigurationError
from zotero_cli.core.services.model_registry import PINNED_MODELS, resolve_model


def test_every_pinned_revision_is_a_full_commit_sha():
    for model in PINNED_MODELS.values():
        assert re.fullmatch(r"[0-9a-f]{40}", model.revision), model.repo_id


def test_known_model_loads_at_its_pinned_revision_without_remote_code():
    load = resolve_model("BAAI/bge-m3")
    assert load.revision == PINNED_MODELS["BAAI/bge-m3"].revision
    assert load.trust_remote_code is False


def test_short_alias_resolves_to_the_pinned_repo():
    load = resolve_model("all-MiniLM-L6-v2")
    assert load.repo_id == "sentence-transformers/all-MiniLM-L6-v2"
    assert load.revision != "main"


def test_remote_code_model_is_refused_without_consent():
    with pytest.raises(ConfigurationError, match="trust_remote_code"):
        resolve_model("jinaai/jina-embeddings-v3")


def test_remote_code_model_loads_with_consent():
    load = resolve_model("jinaai/jina-embeddings-v3", trust_remote_code=True)
    assert load.trust_remote_code is True
    assert load.revision == PINNED_MODELS["jinaai/jina-embeddings-v3"].revision


def test_trust_flag_is_never_passed_to_a_model_that_does_not_need_it():
    assert resolve_model("BAAI/bge-m3", trust_remote_code=True).trust_remote_code is False


def test_unpinned_model_loads_main_with_a_warning(caplog):
    load = resolve_model("someone/custom-model")
    assert load.revision == "main" and load.trust_remote_code is False
    assert "not pinned" in caplog.text


def test_sentence_transformer_provider_passes_revision_and_trust():
    from zotero_cli.core.services.embedding_provider import SentenceTransformerEmbeddingProvider

    fake = MagicMock()
    with patch.dict(sys.modules, {"sentence_transformers": fake}):
        SentenceTransformerEmbeddingProvider("BAAI/bge-m3").model  # noqa: B018 - loads lazily

    kwargs = fake.SentenceTransformer.call_args.kwargs
    assert kwargs["revision"] == PINNED_MODELS["BAAI/bge-m3"].revision
    assert kwargs["trust_remote_code"] is False


def test_config_trust_remote_code_defaults_off(monkeypatch, tmp_path):
    from zotero_cli.core.config import ConfigLoader

    monkeypatch.delenv("ZOTERO_TRUST_REMOTE_CODE", raising=False)
    path = tmp_path / "config.toml"
    path.write_text('[zotero]\nembedding_model = "BAAI/bge-m3"\n')
    assert ConfigLoader(config_path=path).load().trust_remote_code is False

    path.write_text("[zotero]\ntrust_remote_code = true\n")
    assert ConfigLoader(config_path=path).load().trust_remote_code is True

    path.write_text('[zotero]\ntrust_remote_code = "yes"\n')  # only a real boolean counts
    assert ConfigLoader(config_path=path).load().trust_remote_code is False
