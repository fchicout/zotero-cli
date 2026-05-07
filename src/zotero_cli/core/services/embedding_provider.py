from typing import Any, List, Optional, cast

from zotero_cli.core.interfaces import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """
    Dummy embedding provider for tests and development.
    Generates deterministic fake vectors based on text length.
    """

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def embed_text(self, text: str) -> List[float]:
        # Deterministic fake embedding
        val = len(text) / 1000.0
        return [val] * self.dimension

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    Embedding provider using OpenAI API.
    """

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
        try:
            import openai

            self.client: Any = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            self.client = None

    def embed_text(self, text: str) -> List[float]:
        if not self.client:
            raise ImportError("openai package not installed. Run 'pip install openai'")

        response = self.client.embeddings.create(input=text, model=self.model)
        return cast(List[float], response.data[0].embedding)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self.client:
            raise ImportError("openai package not installed. Run 'pip install openai'")

        response = self.client.embeddings.create(input=texts, model=self.model)
        return [cast(List[float], item.embedding) for item in response.data]


class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Embedding provider using Google Gemini API.
    """

    def __init__(self, api_key: str, model: str = "models/text-embedding-004"):
        self.api_key = api_key
        self.model = model
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self.client: Any = genai
        except ImportError:
            self.client = None

    def embed_text(self, text: str) -> List[float]:
        if not self.client:
            raise ImportError(
                "google-generativeai package not installed. Run 'pip install google-generativeai'"
            )

        response = self.client.embed_content(
            model=self.model, content=text, task_type="retrieval_document"
        )
        return cast(List[float], response["embedding"])

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self.client:
            raise ImportError(
                "google-generativeai package not installed. Run 'pip install google-generativeai'"
            )

        response = self.client.embed_content(
            model=self.model, content=texts, task_type="retrieval_document"
        )
        return [cast(List[float], emb) for emb in response["embedding"]]


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """
    Local embedding provider using sentence-transformers.
    Supports any model from Hugging Face.
    Uses lazy loading to avoid heavy memory usage on startup.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", token: Optional[str] = None):
        self.model_name = model_name
        self.token = token
        self._model: Any = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers package not installed. "
                    "Run 'pip install sentence-transformers'"
                )

            # Many 2026 models (Jina v3, Qwen) require trust_remote_code=True
            self._model = SentenceTransformer(
                self.model_name, token=self.token, trust_remote_code=True
            )
        return self._model

    def embed_text(self, text: str) -> List[float]:
        embedding = self.model.encode(text)
        # Handle cases where embedding is a numpy array
        if hasattr(embedding, "tolist"):
            return cast(List[float], embedding.tolist())
        return cast(List[float], list(embedding))

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts)
        if hasattr(embeddings, "tolist"):
            return cast(List[List[float]], embeddings.tolist())
        return cast(List[List[float]], [list(e) for e in embeddings])
