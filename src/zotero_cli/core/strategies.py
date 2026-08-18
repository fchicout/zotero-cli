from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Iterator

from zotero_cli.core.interfaces import (
    ArxivGateway,
    BibtexGateway,
    CanonicalCsvGateway,
    IeeeCsvGateway,
    RisGateway,
    SearchableMetadataProvider,
    SpringerCsvGateway,
)
from zotero_cli.core.models import ResearchPaper

if TYPE_CHECKING:
    from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService


class ImportStrategy(ABC):
    """Abstract base class for all import strategies."""

    @abstractmethod
    def fetch_papers(self, source: str, **kwargs: Any) -> Iterator[ResearchPaper]:
        """Fetch or parse papers from the source."""
        pass


class ArxivImportStrategy(ImportStrategy):
    def __init__(self, gateway: ArxivGateway):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs: Any) -> Iterator[ResearchPaper]:
        limit = kwargs.get("limit", 100)
        sort_by = kwargs.get("sort_by", "relevance")
        sort_order = kwargs.get("sort_order", "descending")
        return self.gateway.search(source, limit, sort_by, sort_order)


class BdtdImportStrategy(ImportStrategy):
    """
    Bulk import from a BDTD free-text/topic search (Issue #182), e.g.
    `import bdtd --query "aprendizado de maquina"`.
    """

    def __init__(self, provider: SearchableMetadataProvider):
        self.provider = provider

    def fetch_papers(self, source: str, **kwargs: Any) -> Iterator[ResearchPaper]:
        limit = kwargs.get("limit", 20)
        return self.provider.search(source, max_results=limit)


class BibtexImportStrategy(ImportStrategy):
    def __init__(self, gateway: BibtexGateway):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs: Any) -> Iterator[ResearchPaper]:
        return self.gateway.parse_file(source)


class RisImportStrategy(ImportStrategy):
    def __init__(self, gateway: RisGateway):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs: Any) -> Iterator[ResearchPaper]:
        return self.gateway.parse_file(source)


class SpringerCsvImportStrategy(ImportStrategy):
    def __init__(self, gateway: SpringerCsvGateway):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs: Any) -> Iterator[ResearchPaper]:
        return self.gateway.parse_file(source)


class IeeeCsvImportStrategy(ImportStrategy):
    def __init__(self, gateway: IeeeCsvGateway):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs: Any) -> Iterator[ResearchPaper]:
        return self.gateway.parse_file(source)


class CanonicalCsvImportStrategy(ImportStrategy):
    def __init__(self, gateway: CanonicalCsvGateway):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs: Any) -> Iterator[ResearchPaper]:
        return self.gateway.parse_file(source)


class DoiImportStrategy(ImportStrategy):
    def __init__(self, aggregator: "MetadataAggregatorService"):
        self.aggregator = aggregator

    def fetch_papers(self, source: str, **kwargs: Any) -> Iterator[ResearchPaper]:
        paper = self.aggregator.get_enriched_metadata(source)
        if paper:
            yield paper
