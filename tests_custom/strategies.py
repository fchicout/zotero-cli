"""Hypothesis strategies for generating test data.

This module provides reusable Hypothesis strategies for generating
valid test data for the CSV-to-BibTeX conversion pipeline.
"""

from hypothesis import strategies as st
from pathlib import Path


@st.composite
def generate_valid_springer_csv(draw, min_entries=1, max_entries=10):
    """Generate valid Springer CSV data.
    
    Args:
        draw: Hypothesis draw function
        min_entries: Minimum number of CSV entries to generate
        max_entries: Maximum number of CSV entries to generate
        
    Returns:
        str: Valid Springer CSV content with header and data rows
        
    The generated CSV includes all required columns:
    - Item Title
    - Authors
    - Publication Year
    - Item DOI
    - URL
    - Content Type
    - Publication Title
    - Journal Volume
    - Journal Issue
    """
    num_entries = draw(st.integers(min_value=min_entries, max_value=max_entries))
    
    # CSV header
    header = "Item Title,Publication Title,Book Series Title,Journal Volume,Journal Issue,Item DOI,Authors,Publication Year,URL,Content Type"
    
    rows = [header]
    
    for i in range(num_entries):
        # Generate realistic field values
        # Use simpler text generation to avoid excessive filtering
        title_words = draw(st.lists(
            st.text(min_size=3, max_size=15, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'),
            min_size=2,
            max_size=10
        ))
        title = ' '.join(title_words)
        
        # Generate authors (may be concatenated)
        authors = draw(generate_concatenated_authors())
        
        # Publication year
        year = draw(st.integers(min_value=1900, max_value=2025))
        
        # DOI
        doi = f"10.{draw(st.integers(min_value=1000, max_value=9999))}/{draw(st.text(min_size=5, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz0123456789-'))}"
        
        # URL
        url = f"https://link.springer.com/article/{doi}"
        
        # Content type
        content_type = draw(st.sampled_from(['Article', 'Conference paper', 'Book Chapter']))
        
        # Journal/Publication title
        journal_words = draw(st.lists(
            st.text(min_size=3, max_size=15, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'),
            min_size=1,
            max_size=5
        ))
        journal = ' '.join(journal_words)
        
        # Volume and issue
        volume = draw(st.integers(min_value=1, max_value=100))
        issue = draw(st.integers(min_value=1, max_value=12))
        
        # Build CSV row (with proper quoting for fields with commas)
        row = f'"{title}","{journal}",,{volume},{issue},{doi},{authors},{year},{url},{content_type}'
        rows.append(row)
    
    return '\n'.join(rows)


@st.composite
def generate_concatenated_authors(draw, min_authors=1, max_authors=5):
    """Generate author names that may be concatenated.
    
    Args:
        draw: Hypothesis draw function
        min_authors: Minimum number of authors
        max_authors: Maximum number of authors
        
    Returns:
        str: Author names, possibly concatenated without separators
        
    This strategy generates author names in various formats:
    - Properly separated: "John Smith and Mary Jones"
    - Concatenated: "John SmithMary Jones"
    - With compound names: "Ronald McDonald"
    - Mixed: "John SmithRonald McDonald"
    """
    num_authors = draw(st.integers(min_value=min_authors, max_value=max_authors))
    
    # Decide if authors should be concatenated
    concatenate = draw(st.booleans())
    
    authors = []
    for _ in range(num_authors):
        # Sometimes use compound names
        use_compound = draw(st.booleans())
        
        if use_compound:
            # Generate compound name
            author = draw(generate_compound_names())
        else:
            # Generate regular name - use simpler approach
            first_name = draw(st.text(min_size=3, max_size=15, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ')) + \
                        draw(st.text(min_size=2, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyz'))
            
            last_name = draw(st.text(min_size=3, max_size=15, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ')) + \
                       draw(st.text(min_size=2, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyz'))
            
            author = f"{first_name} {last_name}"
        
        authors.append(author)
    
    # Join authors with or without separator
    if concatenate:
        # Concatenate without separator
        return ''.join(authors)
    else:
        # Properly separated
        return ' and '.join(authors)


@st.composite
def generate_compound_names(draw):
    """Generate compound names that should be preserved.
    
    Args:
        draw: Hypothesis draw function
        
    Returns:
        str: A compound name like "McDonald", "O'Brien", "MacArthur"
        
    These names have special patterns that should not be split:
    - Mc/Mac prefix: McDonald, MacArthur
    - O' prefix: O'Brien, O'Connor
    - De/Van/Von prefix: De Silva, Van Dyke, Von Neumann
    """
    prefix = draw(st.sampled_from([
        'Mc', 'Mac', "O'", 'De', 'Van', 'Von', 'Di', 'Da', 'La', 'Le'
    ]))
    
    # Generate the rest of the name - use simpler approach
    rest = draw(st.text(min_size=1, max_size=3, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ')) + \
          draw(st.text(min_size=2, max_size=8, alphabet='abcdefghijklmnopqrstuvwxyz'))
    
    # Add first name
    first_name = draw(st.text(min_size=1, max_size=3, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ')) + \
                draw(st.text(min_size=2, max_size=8, alphabet='abcdefghijklmnopqrstuvwxyz'))
    
    return f"{first_name} {prefix}{rest}"


@st.composite
def generate_file_paths(draw, extension=None, max_depth=3):
    """Generate valid file paths.
    
    Args:
        draw: Hypothesis draw function
        extension: Optional file extension (e.g., '.csv', '.bib')
        max_depth: Maximum directory depth
        
    Returns:
        Path: A valid file path
        
    Generates realistic file paths with:
    - Valid filename characters
    - Optional directory structure
    - Optional file extension
    """
    # Generate directory depth
    depth = draw(st.integers(min_value=0, max_value=max_depth))
    
    # Generate directory components - use simpler approach
    dirs = []
    for _ in range(depth):
        dir_name = draw(st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'))
        if dir_name:  # Only add non-empty
            dirs.append(dir_name)
    
    # Generate filename - use simpler approach
    filename = draw(st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'))
    if not filename:  # Ensure non-empty
        filename = 'file'
    
    # Add extension if specified
    if extension:
        if not extension.startswith('.'):
            extension = f'.{extension}'
        filename = f"{filename}{extension}"
    
    # Build path
    if dirs:
        return Path(*dirs) / filename
    else:
        return Path(filename)


@st.composite
def generate_bibtex_entry_type(draw):
    """Generate valid BibTeX entry types.
    
    Args:
        draw: Hypothesis draw function
        
    Returns:
        str: A valid BibTeX entry type
        
    Common BibTeX entry types:
    - article: Journal or magazine article
    - inproceedings: Conference paper
    - book: Published book
    - incollection: Book chapter
    - misc: Miscellaneous
    """
    return draw(st.sampled_from([
        'article',
        'inproceedings',
        'book',
        'incollection',
        'phdthesis',
        'mastersthesis',
        'techreport',
        'misc'
    ]))


@st.composite
def generate_bibtex_key(draw):
    """Generate valid BibTeX citation keys.
    
    Args:
        draw: Hypothesis draw function
        
    Returns:
        str: A valid BibTeX citation key
        
    BibTeX keys typically follow the pattern: Author_Year_Keyword
    """
    # Use simpler approach for author name
    author = draw(st.text(min_size=1, max_size=3, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ')) + \
            draw(st.text(min_size=2, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyz'))
    
    year = draw(st.integers(min_value=1900, max_value=2025))
    
    # Use simpler approach for keyword
    keyword = draw(st.text(min_size=1, max_size=3, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ')) + \
             draw(st.text(min_size=2, max_size=15, alphabet='abcdefghijklmnopqrstuvwxyz'))
    
    return f"{author}_{year}_{keyword}"


# Convenience strategies for common use cases

# Valid CSV filenames - use simpler approach
csv_filenames = st.text(
    min_size=1,
    max_size=50,
    alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
).map(lambda s: f"{s if s else 'file'}.csv")

# Valid BibTeX filenames - use simpler approach
bibtex_filenames = st.text(
    min_size=1,
    max_size=50,
    alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
).map(lambda s: f"{s if s else 'file'}.bib")

# Publication years
publication_years = st.integers(min_value=1900, max_value=2025)

# DOI patterns - use simpler approach
dois = st.builds(
    lambda prefix, suffix: f"10.{prefix}/{suffix if suffix else 'article'}",
    prefix=st.integers(min_value=1000, max_value=9999),
    suffix=st.text(
        min_size=5,
        max_size=30,
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789'
    )
)
