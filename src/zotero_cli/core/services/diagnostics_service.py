import importlib.util
from dataclasses import dataclass
from typing import List, Optional

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.core.interfaces import (
    EmbeddingProvider,
    LLMProvider,
    MetadataProvider,
    ZoteroGateway,
)
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService

# A stable, long-lived DOI used purely as a lightweight connectivity/credential
# probe against metadata providers - not a real research dependency.
_PROBE_DOI = "10.1038/nphys1170"

STATUS_CONNECTED = "CONNECTED"
STATUS_FAILED = "FAILED"
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
STATUS_FOUND = "FOUND"  # the local database, in --offline mode
STATUS_CONFIGURED = "CONFIGURED"  # set up, deliberately not exercised

_CHECK_ZOTERO = "Zotero API"
_CHECK_LOCAL_DB = "Local database"
_KEYS_URL = "https://www.zotero.org/settings/keys"
_RAG_INSTALL = "the rag extra isn't installed: pip install 'zotero-command-line[rag]'"
_CHECK_SEMANTIC_SCHOLAR = "Semantic Scholar"
_CHECK_UNPAYWALL = "Unpaywall"
_CHECK_PUBMED = "PubMed/NCBI"
_CHECK_LLM_PROVIDER = "LLM Provider"
_CHECK_EMBEDDING_PROVIDER = "Embedding Provider"


@dataclass
class CheckResult:
    name: str
    status: str  # STATUS_CONNECTED | STATUS_FAILED | STATUS_NOT_CONFIGURED
    details: str
    # A required check fails `system check` even when NOT_CONFIGURED.
    required: bool = False


class DiagnosticsService:
    """
    Runs lightweight, read-only connectivity/credential checks against every
    external service zotero-cli can be configured to use, for `system check`.
    """

    def __init__(
        self,
        gateway: Optional[ZoteroGateway],
        metadata_aggregator: MetadataAggregatorService,
        llm_provider: Optional[LLMProvider],
        embedding_provider: Optional[EmbeddingProvider],
        config: ZoteroConfig,
        gateway_error: Optional[str] = None,
    ):
        # gateway is None when the library isn't configured; gateway_error
        # says why, and the other checks still run (Issue #376).
        self.gateway = gateway
        self.gateway_error = gateway_error
        self.metadata_aggregator = metadata_aggregator
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider
        self.config = config

    def run_checks(self) -> List[CheckResult]:
        results = [
            self._check_zotero(),
            self._check_semantic_scholar(),
            self._check_unpaywall(),
            self._check_pubmed(),
        ]
        # RAG is an optional extra: its rows appear only when it's configured,
        # and nothing is loaded or called (Issues #408, #382).
        results += self._check_rag_configuration()
        return results

    def _check_zotero(self) -> CheckResult:
        if self.gateway is None:
            return CheckResult(
                _CHECK_ZOTERO,
                STATUS_NOT_CONFIGURED,
                self.gateway_error or "Not configured",
                required=True,
            )
        local_db = getattr(self.gateway, "original_db_path", None)
        if local_db:
            # --offline: the Web API isn't used, so don't claim it was
            # verified (Issue #382); report the database instead.
            try:
                count = self.gateway.count_items()  # type: ignore[attr-defined]
            except Exception as e:
                return CheckResult(_CHECK_LOCAL_DB, STATUS_FAILED, f"{local_db}: {e}")
            return CheckResult(_CHECK_LOCAL_DB, STATUS_FOUND, f"{local_db}, {count} items")
        try:
            if self.gateway.verify_credentials():
                return CheckResult(_CHECK_ZOTERO, STATUS_CONNECTED, "Credentials verified")
            return CheckResult(
                _CHECK_ZOTERO,
                STATUS_FAILED,
                f"API key rejected: create one at {_KEYS_URL}, then run `zotero-cli init`",
            )
        except Exception as e:
            # A network failure or rate limit, not a rejected key (Issue #408).
            return CheckResult(_CHECK_ZOTERO, STATUS_FAILED, str(e))

    def _check_semantic_scholar(self) -> CheckResult:
        if not self.config.semantic_scholar_api_key:
            return CheckResult(
                _CHECK_SEMANTIC_SCHOLAR,
                STATUS_NOT_CONFIGURED,
                "No API key set (works anonymously, rate-limited)",
            )
        return self._probe_metadata_client(
            _CHECK_SEMANTIC_SCHOLAR, self.metadata_aggregator.semantic_scholar
        )

    def _check_unpaywall(self) -> CheckResult:
        if not self.config.unpaywall_email:
            return CheckResult(_CHECK_UNPAYWALL, STATUS_NOT_CONFIGURED, "No contact email set")
        return self._probe_metadata_client(_CHECK_UNPAYWALL, self.metadata_aggregator.unpaywall)

    def _check_pubmed(self) -> CheckResult:
        if not self.config.ncbi_api_key:
            return CheckResult(
                _CHECK_PUBMED,
                STATUS_NOT_CONFIGURED,
                "No NCBI key set (works anonymously, rate-limited)",
            )
        return self._probe_metadata_client(_CHECK_PUBMED, self.metadata_aggregator.pubmed)

    def _probe_metadata_client(
        self, name: str, client: Optional[MetadataProvider]
    ) -> CheckResult:
        # These clients never raise - they catch every error internally and
        # return None, so a None response (not an exception) is the failure
        # signal here. The try/except is still a defensive backstop.
        if client is None:
            return CheckResult(name, STATUS_FAILED, "Client not initialized")
        try:
            result = client.get_paper_metadata(_PROBE_DOI)
        except Exception as e:
            return CheckResult(name, STATUS_FAILED, str(e))
        if result is None:
            return CheckResult(
                name, STATUS_FAILED, "No response (check network/API key/rate limit)"
            )
        return CheckResult(name, STATUS_CONNECTED, "Reachable")

    def _check_rag_configuration(self) -> List[CheckResult]:
        """The configured RAG providers, reported without loading a model,
        downloading weights or calling an API: `system check` used to do
        all three (Issue #382) and showed a FAILED row on every install
        without the optional extra (Issue #408)."""
        c = self.config
        rows: List[CheckResult] = []
        embedding = (c.embedding_provider or "auto").lower()
        if embedding != "auto" or c.embedding_model:
            rows.append(
                self._rag_row(
                    _CHECK_EMBEDDING_PROVIDER,
                    embedding,
                    c.embedding_model,
                    {"local": "sentence_transformers", "openai": "openai",
                     "gemini": "google.generativeai"},
                )
            )
        generative = (c.generative_provider or "auto").lower()
        if generative != "auto" or c.generative_model:
            rows.append(
                self._rag_row(
                    _CHECK_LLM_PROVIDER,
                    generative,
                    c.generative_model,
                    {"local": "transformers", "openai": "openai", "gemini": "google.generativeai"},
                )
            )
        return rows

    @staticmethod
    def _rag_row(name: str, provider: str, model: Optional[str], modules: dict) -> CheckResult:
        module = modules.get(provider)
        if module and not _importable(module):
            return CheckResult(name, STATUS_FAILED, _RAG_INSTALL)
        label = f"{provider}" + (f": {model}" if model else "")
        return CheckResult(name, STATUS_CONFIGURED, f"{label} (not loaded; `rag query` uses it)")


def _importable(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False
