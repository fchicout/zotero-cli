"""CSV to BibTeX converter for Springer search results.

This module provides the core conversion logic for transforming Springer CSV
export files into properly formatted BibTeX bibliography files.
"""

import re
import html
from pathlib import Path
from typing import List, Dict, Set
from unicodedata import normalize

from custom.core.models import BibTeXEntry, ConversionResult
from custom.utils.file_handler import FileHandler


class CSVConverter:
    """Converts Springer CSV files to BibTeX format.
    
    This class encapsulates the logic for parsing Springer CSV export files
    and generating properly formatted BibTeX entries. It handles text cleaning,
    special character escaping, unique key generation, and multi-file output
    when dealing with large datasets.
    
    Attributes:
        entries_per_file: Maximum number of entries per output file (default: 49)
    """
    
    def __init__(self, entries_per_file: int = 49):
        """Initialize the CSV converter.
        
        Args:
            entries_per_file: Maximum number of BibTeX entries per output file.
                             Files are split to avoid memory issues with large datasets.
        """
        self.entries_per_file = entries_per_file
    
    def convert(self, csv_path: Path, output_dir: Path, output_base_name: str = None) -> ConversionResult:
        """Convert CSV file to BibTeX files.
        
        Main entry point for the conversion process. Reads a Springer CSV file,
        converts each row to a BibTeX entry, and writes the results to one or
        more output files in the specified directory.
        
        Args:
            csv_path: Path to the input Springer CSV file
            output_dir: Directory where BibTeX files should be written
            output_base_name: Base name for output files (without extension).
                            If None, uses the input filename stem.
                            Example: "my_results" creates "my_results.bib" or 
                            "my_results_part1.bib", "my_results_part2.bib", etc.
            
        Returns:
            ConversionResult containing success status, entry count, output files,
            and any errors encountered during conversion
            
        Raises:
            FileNotFoundError: If the CSV file does not exist
            ValueError: If the CSV file is invalid or cannot be parsed
        """
        errors = []
        entries = []
        used_keys: Set[str] = set()
        
        try:
            # Read CSV file using FileHandler (Requirement 7.1)
            rows = FileHandler.read_csv(csv_path)
            
            # Process each row
            for row_num, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
                try:
                    entry = self._parse_csv_row(row, used_keys)
                    if entry:
                        entries.append(entry)
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    continue
            
            # Generate output files
            # Use provided base name, or derive from input filename
            if output_base_name is None:
                # Remove extension and use input filename
                output_base_name = csv_path.stem
            
            output_files = self._write_bibtex_files(
                entries, 
                output_dir, 
                output_base_name
            )
            
            return ConversionResult(
                success=len(entries) > 0,
                entries_count=len(entries),
                output_files=output_files,
                errors=errors
            )
            
        except Exception as e:
            return ConversionResult(
                success=False,
                entries_count=0,
                output_files=[],
                errors=[f"Conversion failed: {str(e)}"]
            )
    
    def _parse_csv_row(self, row: Dict[str, str], used_keys: Set[str]) -> BibTeXEntry:
        """Parse a single CSV row into a BibTeXEntry object.
        
        Extracts bibliographic information from a Springer CSV row and creates
        a structured BibTeXEntry. Handles missing fields gracefully and ensures
        unique keys.
        
        Args:
            row: Dictionary representing a CSV row with column headers as keys
            used_keys: Set of already-used BibTeX keys to ensure uniqueness
            
        Returns:
            BibTeXEntry object, or None if the row should be skipped
        """
        # Extract and clean data
        title = self._clean_text(row.get('Item Title', ''))
        authors = row.get('Authors', '').strip()
        year = row.get('Publication Year', '').strip()
        doi = row.get('Item DOI', '').strip()
        url = row.get('URL', '').strip()
        content_type = row.get('Content Type', 'Article')
        
        # Additional fields
        journal = self._clean_text(row.get('Publication Title', ''))
        book_series = self._clean_text(row.get('Book Series Title', ''))
        volume = row.get('Journal Volume', '').strip()
        issue = row.get('Journal Issue', '').strip()
        
        # Skip empty entries
        if not title:
            return None
        
        # Create unique BibTeX key (Requirement 2.1)
        key = self._create_bibtex_key(authors, year, title, used_keys)
        used_keys.add(key)
        
        # Determine entry type
        entry_type = self._get_entry_type(content_type)
        
        # Use journal or book series as appropriate
        if entry_type == 'inproceedings' and book_series:
            journal = book_series
        
        return BibTeXEntry(
            key=key,
            entry_type=entry_type,
            title=title,
            authors=authors if authors else "Anonymous",
            year=year,
            doi=doi,
            url=url,
            journal=journal,
            volume=volume,
            issue=issue,
            publisher="Springer"
        )
    
    def _create_bibtex_key(
        self, 
        authors: str, 
        year: str, 
        title: str,
        used_keys: Set[str]
    ) -> str:
        """Generate unique BibTeX key for an entry.
        
        Creates a key in the format: LastName_Year_FirstWord
        Ensures uniqueness by appending a counter if needed.
        
        Args:
            authors: Author string from CSV
            year: Publication year
            title: Paper title
            used_keys: Set of already-used keys
            
        Returns:
            Unique BibTeX key string
        """
        # Get first author's last name
        if authors:
            # Try to extract first surname (capitalized word)
            match = re.search(r'([A-Z][a-z]+)\b', authors)
            last_name = match.group(1) if match else 'Unknown'
        else:
            last_name = 'Unknown'
        
        # Get first meaningful word of title (>3 chars)
        title_words = [w for w in re.findall(r'\w+', title) if len(w) > 3]
        first_word = title_words[0] if title_words else 'paper'
        
        # Create base key: LastName_Year_FirstWord
        base_key = f"{last_name}_{year}_{first_word}"
        
        # Remove special characters and make safe
        base_key = re.sub(r'[^a-zA-Z0-9_]', '', base_key)
        
        # Ensure uniqueness
        key = base_key
        counter = 1
        while key in used_keys:
            key = f"{base_key}{counter}"
            counter += 1
        
        return key
    
    def _format_entry(self, entry: BibTeXEntry) -> str:
        """Convert BibTeXEntry object to BibTeX string format.
        
        Generates a properly formatted BibTeX entry string with all fields
        that have values. Handles special characters and follows BibTeX
        formatting conventions.
        
        Args:
            entry: BibTeXEntry object to format
            
        Returns:
            Formatted BibTeX entry as a string
        """
        # Start entry with type and key
        lines = [f"@{entry.entry_type}{{{entry.key},"]
        
        # Add title
        lines.append(f"  title = {{{entry.title}}},")
        
        # Add authors
        lines.append(f"  author = {{{entry.authors}}},")
        
        # Add year
        if entry.year:
            lines.append(f"  year = {{{entry.year}}},")
        
        # Add DOI
        if entry.doi:
            lines.append(f"  doi = {{{entry.doi}}},")
        
        # Add URL
        if entry.url:
            lines.append(f"  url = {{{entry.url}}},")
        
        # Add journal/booktitle based on type
        if entry.entry_type == 'article' and entry.journal:
            lines.append(f"  journal = {{{entry.journal}}},")
        elif entry.entry_type == 'inproceedings' and entry.journal:
            lines.append(f"  booktitle = {{{entry.journal}}},")
        elif entry.journal:
            lines.append(f"  journal = {{{entry.journal}}},")
        
        # Add volume
        if entry.volume:
            lines.append(f"  volume = {{{entry.volume}}},")
        
        # Add issue/number
        if entry.issue:
            lines.append(f"  number = {{{entry.issue}}},")
        
        # Add publisher
        if entry.publisher:
            lines.append(f"  publisher = {{{entry.publisher}}},")
        
        # Remove trailing comma from last field and close entry
        if lines[-1].endswith(','):
            lines[-1] = lines[-1][:-1]
        
        lines.append("}")
        
        return "\n".join(lines)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for BibTeX.
        
        Performs text normalization including HTML entity decoding,
        Unicode normalization, and LaTeX-compatible dash replacement.
        
        Args:
            text: Raw text string to clean
            
        Returns:
            Cleaned and normalized text
        """
        if not text:
            return ""
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Normalize unicode characters
        text = normalize('NFKD', text)
        
        # Replace em/en dashes with LaTeX equivalents
        text = text.replace('–', '--').replace('—', '---')
        
        return text.strip()
    
    def _escape_bibtex_special_chars(self, text: str) -> str:
        """Escape special characters for BibTeX.
        
        Protects special characters that have meaning in BibTeX/LaTeX
        by adding backslash escapes. Skips text that already contains
        LaTeX commands.
        
        Args:
            text: Text that may contain special characters
            
        Returns:
            Text with special characters escaped
        """
        # Don't escape if already appears to be LaTeX
        if '\\' in text:
            return text
        
        # Escape special chars
        replacements = {
            '&': '\\&',
            '%': '\\%',
            '$': '\\$',
            '#': '\\#',
            '_': '\\_',
            '{': '\\{',
            '}': '\\}',
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    def _get_entry_type(self, content_type: str) -> str:
        """Map Springer content type to BibTeX entry type.
        
        Converts Springer's content type classification to the appropriate
        BibTeX entry type (article, inproceedings, book, etc.).
        
        Args:
            content_type: Content type string from Springer CSV
            
        Returns:
            BibTeX entry type string
        """
        content_type_lower = content_type.lower()
        
        if 'conference' in content_type_lower:
            return 'inproceedings'
        elif 'article' in content_type_lower or 'review' in content_type_lower:
            return 'article'
        elif 'chapter' in content_type_lower:
            return 'incollection'  # Book chapter
        elif 'book' in content_type_lower:
            return 'book'
        elif 'reference work' in content_type_lower:
            return 'inreference'  # Encyclopedia/reference entries
        else:
            return 'misc'
    
    def _write_bibtex_files(
        self,
        entries: List[BibTeXEntry],
        output_dir: Path,
        base_name: str
    ) -> List[Path]:
        """Write BibTeX entries to one or more output files.
        
        Splits entries across multiple files if needed to maintain the
        entries_per_file limit. Files are named with part numbers when
        multiple files are created (Requirement 2.2, 7.4).
        
        Args:
            entries: List of BibTeXEntry objects to write
            output_dir: Directory where files should be written
            base_name: Base name for output files (without extension)
            
        Returns:
            List of Path objects for created files
        """
        total_entries = len(entries)
        num_files = (total_entries + self.entries_per_file - 1) // self.entries_per_file
        
        output_files = []
        
        for i in range(num_files):
            start_idx = i * self.entries_per_file
            end_idx = min((i + 1) * self.entries_per_file, total_entries)
            chunk = entries[start_idx:end_idx]
            
            # Create filename with part number (Requirement 2.2)
            if num_files > 1:
                output_file = output_dir / f"{base_name}_part{i+1}.bib"
            else:
                output_file = output_dir / f"{base_name}.bib"
            
            # Format entries as BibTeX strings
            bibtex_content = "\n\n".join(
                self._format_entry(entry) for entry in chunk
            )
            
            # Write to file using FileHandler (Requirement 7.3)
            FileHandler.write_bibtex(output_file, bibtex_content)
            
            output_files.append(output_file)
        
        return output_files

