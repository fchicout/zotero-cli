from typing import List, cast

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

            self.client = openai.OpenAI(api_key=self.api_key)
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
            self.client = genai
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
