from unittest.mock import MagicMock, patch

from zotero_cli.core.services.embedding_provider import (
    GeminiEmbeddingProvider,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    is_api_retryable,
)


def test_is_api_retryable():
    # Test retryable exceptions for openai and google
    import sys

    class MockRateLimitError(Exception):
        pass
    class MockInternalServerError(Exception):
        pass
    class MockResourceExhausted(Exception):
        pass
    class MockServiceUnavailable(Exception):
        pass

    # Mock exceptions
    openai_mock = MagicMock()
    openai_mock.RateLimitError = MockRateLimitError
    openai_mock.InternalServerError = MockInternalServerError

    google_mock = MagicMock()
    google_mock.ResourceExhausted = MockResourceExhausted
    google_mock.InternalServerError = MockInternalServerError
    google_mock.ServiceUnavailable = MockServiceUnavailable

    with patch.dict(sys.modules, {"openai": openai_mock, "google.api_core.exceptions": google_mock}):
        assert is_api_retryable(openai_mock.RateLimitError()) is True
        assert is_api_retryable(openai_mock.InternalServerError()) is True
        assert is_api_retryable(Exception()) is False




def test_mock_embedding_provider():
    provider = MockEmbeddingProvider(dimension=10)
    emb = provider.embed_text("hello")
    assert len(emb) == 10
    assert emb[0] == len("hello") / 1000.0

    batch = provider.embed_batch(["hello", "world"])
    assert len(batch) == 2
    assert len(batch[0]) == 10


def test_openai_embedding_provider():
    # Mock openai client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_item = MagicMock()
    mock_item.embedding = [0.1, 0.2]
    mock_response.data = [mock_item]
    mock_client.embeddings.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        provider = OpenAIEmbeddingProvider(api_key="test_key")
        emb = provider.embed_text("hello")
        assert emb == [0.1, 0.2]

        # batch
        mock_item2 = MagicMock()
        mock_item2.embedding = [0.3, 0.4]
        mock_response.data = [mock_item, mock_item2]
        batch = provider.embed_batch(["hello", "world"])
        assert batch == [[0.1, 0.2], [0.3, 0.4]]


def test_gemini_embedding_provider():
    mock_genai = MagicMock()
    mock_genai.embed_content.return_value = {"embedding": [0.5, 0.6]}

    with patch("google.generativeai.embed_content", mock_genai.embed_content):
        provider = GeminiEmbeddingProvider(api_key="test_key")
        provider.client = mock_genai
        emb = provider.embed_text("hello")
        assert emb == [0.5, 0.6]

        # batch
        mock_genai.embed_content.return_value = {"embedding": [[0.5, 0.6], [0.7, 0.8]]}
        batch = provider.embed_batch(["hello", "world"])
        assert batch == [[0.5, 0.6], [0.7, 0.8]]


def test_sentence_transformer_embedding_provider():
    mock_model = MagicMock()
    mock_model.encode.return_value = MagicMock(tolist=lambda: [0.9, 0.99])

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        provider = SentenceTransformerEmbeddingProvider(model_name="all-MiniLM-L6-v2")
        emb = provider.embed_text("hello")
        assert emb == [0.9, 0.99]

        mock_model.encode.return_value = MagicMock(tolist=lambda: [[0.9, 0.99], [0.8, 0.88]])
        batch = provider.embed_batch(["hello", "world"])
        assert batch == [[0.9, 0.99], [0.8, 0.88]]
