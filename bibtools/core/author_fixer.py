"""Author name fixing logic for BibTeX files.

This module provides functionality to fix concatenated author names in BibTeX files.
It separates names that are stuck together (e.g., "John SmithMary Jones" -> "John Smith and Mary Jones")
while preserving compound names like McDonald, O'Brien, etc.

This is a direct adaptation of scripts/utils/fix_bibtex_authors_claude.py
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

from .models import ConversionResult


class AuthorFixer:
    """Fixes concatenated author names in BibTeX files.
    
    This class encapsulates the logic from the original fix_bibtex_authors_claude.py script.
    It uses heuristics to detect where names are concatenated by looking for patterns where
    a lowercase letter is followed by an uppercase letter, while preserving compound names.
    """
    
    # Compound name patterns that should NOT be separated (from original script)
    # Format: (pattern, temporary replacement)
    COMPOUND_PATTERNS = [
        (r'McDonald', '__MCDONALD__'),
        (r'MacArthur', '__MACARTHUR__'),
        (r'McC[a-z]+', '__MCC__'),
        (r'DeL[a-z]+', '__DEL__'),
        (r"O'[A-Z][a-z]+", '__OAPOS__'),
    ]
    
    def fix_file(self, input_path: Path, output_path: Path) -> ConversionResult:
        """Process a BibTeX file and fix author fields.
        
        Args:
            input_path: Path to the input BibTeX file
            output_path: Path where the fixed BibTeX file should be saved
            
        Returns:
            ConversionResult with success status, correction count, and output files
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            PermissionError: If unable to read input or write output
        """
        if not input_path.exists():
            return ConversionResult(
                success=False,
                entries_count=0,
                output_files=[],
                errors=[f"Input file not found: {input_path}"]
            )
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except PermissionError as e:
            return ConversionResult(
                success=False,
                entries_count=0,
                output_files=[],
                errors=[f"Permission denied reading file: {input_path}"]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                entries_count=0,
                output_files=[],
                errors=[f"Error reading file {input_path}: {str(e)}"]
            )
        
        lines = content.split('\n')
        fixed_lines = []
        corrections = 0
        errors = []
        
        for i, line in enumerate(lines):
            # Check if it's an author line
            if re.match(r'\s*author\s*=\s*\{', line, re.IGNORECASE):
                # Extract the content of the author field
                match = re.match(r'(\s*author\s*=\s*\{)(.+?)(\},?\s*)$', line, re.IGNORECASE)
                if match:
                    prefix = match.group(1)
                    authors = match.group(2)
                    suffix = match.group(3)
                    
                    # Fix the authors
                    fixed_authors = self.fix_author_string(authors)
                    
                    if fixed_authors != authors:
                        corrections += 1
                        # Check if the correction seems reasonable
                        num_authors = len(fixed_authors.split(' and '))
                        if num_authors > 20:  # Something probably went wrong
                            errors.append(
                                f"Line {i + 1} may need manual review: "
                                f"resulted in {num_authors} authors"
                            )
                    
                    fixed_line = f"{prefix}{fixed_authors}{suffix}"
                    fixed_lines.append(fixed_line)
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the fixed file
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(fixed_lines))
        except PermissionError:
            return ConversionResult(
                success=False,
                entries_count=corrections,
                output_files=[],
                errors=[f"Permission denied writing file: {output_path}"]
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                entries_count=corrections,
                output_files=[],
                errors=[f"Error writing file {output_path}: {str(e)}"]
            )
        
        return ConversionResult(
            success=True,
            entries_count=corrections,
            output_files=[output_path],
            errors=errors
        )
    
    def fix_author_string(self, author_string: str) -> str:
        """Separate concatenated author names.
        
        Uses heuristics to detect where names are concatenated by looking for
        patterns where a lowercase letter is followed by an uppercase letter.
        Preserves compound names like McDonald, O'Brien, etc.
        
        Args:
            author_string: The author field content to fix
            
        Returns:
            Fixed author string with proper " and " separators
        """
        # If it's "Anonymous" or a single author without concatenation
        if author_string.strip() in ["Anonymous", "anonymous"]:
            return author_string
        
        # Protect compound names
        result, protected_map = self._protect_compound_names(author_string)
        
        # Split concatenated names
        result = self._split_concatenated(result)
        
        # Restore protected patterns
        result = self._restore_protected_names(result, protected_map)
        
        # Final cleanup
        result = re.sub(r'\s+and\s+and\s+', ' and ', result)
        result = re.sub(r'\s+', ' ', result)
        result = re.sub(r'^\s*and\s+', '', result)  # Remove "and" at the beginning
        result = re.sub(r'\s+and\s*$', '', result)  # Remove "and" at the end
        
        return result.strip()
    
    def _protect_compound_names(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Protect compound names like McDonald, O'Brien from being split.
        
        Replaces compound name patterns with temporary placeholders to prevent
        them from being incorrectly split during concatenation detection.
        
        Args:
            text: The text containing author names
            
        Returns:
            Tuple of (protected text with placeholders, mapping of placeholders to originals)
        """
        result = text
        protected_map = {}
        
        for pattern, placeholder in self.COMPOUND_PATTERNS:
            matches = re.findall(pattern, result)
            for i, match in enumerate(matches):
                key = f"{placeholder}{i}__"
                protected_map[key] = match
                result = result.replace(match, key, 1)
        
        return result, protected_map
    
    def _split_concatenated(self, text: str) -> str:
        """Split names at lowercase-to-uppercase boundaries.
        
        Detects concatenated names by finding transitions from lowercase letters,
        numbers, periods, or closing parentheses to uppercase letters, and inserts
        " and " separators at those boundaries.
        
        Args:
            text: The text with protected compound names
            
        Returns:
            Text with " and " separators inserted at concatenation points
        """
        # Separates where there's lowercase/number/period/parenthesis followed by uppercase
        # Makes multiple passes to ensure all cases are captured
        prev_result = ""
        result = text
        
        while prev_result != result:
            prev_result = result
            result = re.sub(
                r'([a-zçãõáéíóúâêîôûàèìòùäëïöü0-9\.\)\]])([A-Z])',
                r'\1 and \2',
                result
            )
        
        return result
    
    def _restore_protected_names(self, text: str, protected_map: Dict[str, str]) -> str:
        """Restore compound names from placeholders.
        
        Replaces temporary placeholders with the original compound names.
        
        Args:
            text: Text with placeholders
            protected_map: Mapping of placeholders to original compound names
            
        Returns:
            Text with compound names restored
        """
        result = text
        for placeholder, original in protected_map.items():
            result = result.replace(placeholder, original)
        return result
