from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.embedding_provider import GeminiEmbeddingProvider


def test_gemini_embed_text():
    provider = GeminiEmbeddingProvider(api_key="test_key")
    provider.client = MagicMock()
    provider.client.embed_content.return_value = {"embedding": [0.1, 0.2, 0.3]}

    result = provider.embed_text("hello")

    assert result == [0.1, 0.2, 0.3]
    provider.client.embed_content.assert_called_once_with(
        model="models/text-embedding-004", content="hello", task_type="retrieval_document"
    )


def test_gemini_embed_batch():
    provider = GeminiEmbeddingProvider(api_key="test_key")
    provider.client = MagicMock()
    provider.client.embed_content.return_value = {"embedding": [[0.1], [0.2]]}

    result = provider.embed_batch(["a", "b"])

    assert result == [[0.1], [0.2]]
    provider.client.embed_content.assert_called_once_with(
        model="models/text-embedding-004",
        content=["a", "b"],
        task_type="retrieval_document",
    )


def test_gemini_import_error():
    provider = GeminiEmbeddingProvider(api_key="test_key")
    provider.client = None

    with pytest.raises(ImportError) as exc:
        provider.embed_text("foo")
    assert "google-generativeai package not installed" in str(exc.value)
