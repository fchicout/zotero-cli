"""Data models for CSV to BibTeX conversion."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class BibTeXEntry:
    """Represents a single BibTeX entry.
    
    This model encapsulates all the bibliographic information needed
    to generate a properly formatted BibTeX entry.
    """
    key: str
    entry_type: str
    title: str
    authors: str
    year: str
    doi: str
    url: str
    journal: str
    volume: str
    issue: str
    publisher: str


@dataclass
class ConversionResult:
    """Result of a conversion operation.
    
    Encapsulates the outcome of CSV to BibTeX conversion or author fixing,
    including success status, metrics, and any errors encountered.
    """
    success: bool
    entries_count: int
    output_files: List[Path]
    errors: List[str]


@dataclass
class ErrorResponse:
    """Standardized error response.
    
    Provides a consistent structure for error reporting across
    the conversion pipeline.
    """
    success: bool = False
    error_type: str = ""
    message: str = ""
    details: Optional[dict] = None
