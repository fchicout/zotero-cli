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

_CHECK_ZOTERO = "Zotero API"
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


class DiagnosticsService:
    """
    Runs lightweight, read-only connectivity/credential checks against every
    external service zotero-cli can be configured to use, for `system check`.
    """

    def __init__(
        self,
        gateway: ZoteroGateway,
        metadata_aggregator: MetadataAggregatorService,
        llm_provider: Optional[LLMProvider],
        embedding_provider: EmbeddingProvider,
        config: ZoteroConfig,
    ):
        self.gateway = gateway
        self.metadata_aggregator = metadata_aggregator
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider
        self.config = config

    def run_checks(self) -> List[CheckResult]:
        return [
            self._check_zotero(),
            self._check_semantic_scholar(),
            self._check_unpaywall(),
            self._check_pubmed(),
            self._check_llm_provider(),
            self._check_embedding_provider(),
        ]

    def _check_zotero(self) -> CheckResult:
        try:
            if self.gateway.verify_credentials():
                return CheckResult(_CHECK_ZOTERO, STATUS_CONNECTED, "Credentials verified")
            return CheckResult(_CHECK_ZOTERO, STATUS_FAILED, "Credentials rejected")
        except Exception as e:
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

    def _check_llm_provider(self) -> CheckResult:
        if self.llm_provider is None:
            return CheckResult(_CHECK_LLM_PROVIDER, STATUS_NOT_CONFIGURED, "No provider configured")
        try:
            self.llm_provider.generate("Reply with the single word: pong")
            return CheckResult(
                _CHECK_LLM_PROVIDER, STATUS_CONNECTED, type(self.llm_provider).__name__
            )
        except Exception as e:
            return CheckResult(_CHECK_LLM_PROVIDER, STATUS_FAILED, str(e))

    def _check_embedding_provider(self) -> CheckResult:
        try:
            self.embedding_provider.embed_text("ping")
            return CheckResult(
                _CHECK_EMBEDDING_PROVIDER, STATUS_CONNECTED, type(self.embedding_provider).__name__
            )
        except Exception as e:
            return CheckResult(_CHECK_EMBEDDING_PROVIDER, STATUS_FAILED, str(e))
