from typing import TYPE_CHECKING, Optional

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.infra.repository_factory import RepositoryFactory

if TYPE_CHECKING:
    from zotero_cli.core.interfaces import (
        EmbeddingProvider,
        LLMProvider,
        RAGService,
        VectorRepository,
    )
    from zotero_cli.core.services.speech_service import SpeechService


class AIProviderFactory:
    """
    Constructs the RAG subsystem's dependencies: the vector store, the
    embedding/LLM providers (local, OpenAI, or Gemini depending on config),
    the composed RAGService, and the text-to-speech service.
    """

    @staticmethod
    def get_vector_repository(config: Optional[ZoteroConfig] = None) -> "VectorRepository":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        from zotero_cli.core.config import get_storage_dir

        db_dir = get_storage_dir()
        db_dir.mkdir(parents=True, exist_ok=True)

        # Use library_id or default name to isolate projects
        library_suffix = config.library_id if config and config.library_id else "default"
        db_path = str(db_dir / f"vector_store_{library_suffix}.sqlite")

        from zotero_cli.infra.sqlite_vector_repo import SQLiteVectorRepository

        return SQLiteVectorRepository(db_path)

    @staticmethod
    def get_embedding_provider(config: Optional[ZoteroConfig] = None) -> "EmbeddingProvider":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        from zotero_cli.core.services.embedding_provider import (
            GeminiEmbeddingProvider,
            MockEmbeddingProvider,
            OpenAIEmbeddingProvider,
            SentenceTransformerEmbeddingProvider,
        )

        provider_type = config.embedding_provider.lower()
        model_name = config.embedding_model

        if provider_type == "local":
            return SentenceTransformerEmbeddingProvider(
                model_name or "all-MiniLM-L6-v2", token=config.huggingface_token
            )

        if config.gemini_api_key and provider_type in ["auto", "gemini"]:
            return GeminiEmbeddingProvider(config.gemini_api_key)

        if config.openai_api_key and provider_type in ["auto", "openai"]:
            return OpenAIEmbeddingProvider(config.openai_api_key)

        if provider_type == "mock":
            return MockEmbeddingProvider()

        # Default to local if no API keys but and we haven't explicitly asked for mock
        return SentenceTransformerEmbeddingProvider(
            model_name or "all-MiniLM-L6-v2", token=config.huggingface_token
        )

    @staticmethod
    def get_llm_provider(config: Optional[ZoteroConfig] = None) -> Optional["LLMProvider"]:
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        from zotero_cli.core.services.llm_provider import (
            GeminiLLMProvider,
            LocalTransformersLLMProvider,
            MockLLMProvider,
            OpenAILLMProvider,
        )

        provider_type = config.generative_provider.lower()
        model_name = config.generative_model

        if provider_type == "local":
            return LocalTransformersLLMProvider(model_name or "Qwen/Qwen2.5-1.5B-Instruct")

        if config.gemini_api_key and provider_type in ["auto", "gemini"]:
            return GeminiLLMProvider(config.gemini_api_key)

        if config.openai_api_key and provider_type in ["auto", "openai"]:
            return OpenAILLMProvider(config.openai_api_key)

        if provider_type == "mock":
            return MockLLMProvider()

        # If no keys and auto, but we have local model name, fallback to local
        if model_name and provider_type == "auto":
            return LocalTransformersLLMProvider(model_name)

        return None

    @staticmethod
    def get_rag_service(
        config: Optional[ZoteroConfig] = None,
        force_user: bool = False,
        offline: Optional[bool] = None,
    ) -> "RAGService":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        gateway = RepositoryFactory.get_zotero_gateway(config, force_user, offline=offline)
        vector_repo = AIProviderFactory.get_vector_repository(config)
        embedding_provider = AIProviderFactory.get_embedding_provider(config)
        llm_provider = AIProviderFactory.get_llm_provider(config)

        from zotero_cli.infra.service_factory import ServiceFactory

        attachment_service = ServiceFactory.get_attachment_service(
            config, force_user, offline=offline
        )
        orchestrator = ServiceFactory.get_slr_orchestrator(config, force_user, offline=offline)
        citation_service = ServiceFactory.get_citation_service()

        from zotero_cli.core.services.rag_service import MarkdownRecursiveSplitter, RAGServiceBase

        return RAGServiceBase(
            gateway,
            vector_repo,
            embedding_provider,
            attachment_service,
            orchestrator=orchestrator,
            citation_service=citation_service,
            text_splitter=MarkdownRecursiveSplitter(chunk_size=1500),
            llm_provider=llm_provider,
        )

    @staticmethod
    def get_speech_service(config: Optional[ZoteroConfig] = None) -> "SpeechService":
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()

        from zotero_cli.core.services.speech_service import KokoroSpeechProvider, SpeechService
        from zotero_cli.core.utils.speech_filter import TextCleaningFilter

        provider = KokoroSpeechProvider(
            lang_code=config.tts_lang or "a", voice=config.tts_voice or "af_heart"
        )

        return SpeechService(provider, TextCleaningFilter())
