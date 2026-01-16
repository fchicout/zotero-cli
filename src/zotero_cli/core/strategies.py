from abc import ABC, abstractmethod
from typing import Any, Iterator

from zotero_cli.core.interfaces import (
    ArxivGateway,
    BibtexGateway,
    IeeeCsvGateway,
    RisGateway,
    SpringerCsvGateway,
)
from zotero_cli.core.models import ResearchPaper


class ImportStrategy(ABC):
    """Abstract base class for all import strategies."""

    @abstractmethod
    def fetch_papers(self, source: str, **kwargs) -> Iterator[ResearchPaper]:
        """Fetch or parse papers from the source."""
        pass

class ArxivImportStrategy(ImportStrategy):
    def __init__(self, gateway: ArxivGateway):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs) -> Iterator[ResearchPaper]:
        limit = kwargs.get('limit', 100)
        sort_by = kwargs.get('sort_by', 'relevance')
        sort_order = kwargs.get('sort_order', 'descending')
        return self.gateway.search(source, limit, sort_by, sort_order)

class BibtexImportStrategy(ImportStrategy):
    def __init__(self, gateway: BibtexGateway):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs) -> Iterator[ResearchPaper]:
        return self.gateway.parse_file(source)

class RisImportStrategy(ImportStrategy):
    def __init__(self, gateway: RisGateway):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs) -> Iterator[ResearchPaper]:
        return self.gateway.parse_file(source)

class SpringerCsvImportStrategy(ImportStrategy):
    def __init__(self, gateway: SpringerCsvGateway):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs) -> Iterator[ResearchPaper]:
        return self.gateway.parse_file(source)

class IeeeCsvImportStrategy(ImportStrategy):
    def __init__(self, gateway: IeeeCsvGateway):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs) -> Iterator[ResearchPaper]:
        return self.gateway.parse_file(source)

class CanonicalCsvImportStrategy(ImportStrategy):
    def __init__(self, gateway: Any):
        self.gateway = gateway

    def fetch_papers(self, source: str, **kwargs) -> Iterator[ResearchPaper]:
        return self.gateway.parse_file(source)
