#!/usr/bin/env python3
"""
Utility functions for Audiobookshelf Metadata Harmony Agent

Provides:
- calculate_completeness_score(book) - Weighted scoring of metadata completeness
- is_semantically_equivalent(val1, val2, field_type) - Semantic equality checking
- Field weight definitions and normalization helpers
"""

import re
from datetime import datetime
from typing import Any, Optional, List
from rapidfuzz import fuzz

from harmony_models import BookMetadata


# Field importance weights (0.0-1.0)
# Higher weight = more critical for completeness score
FIELD_WEIGHTS = {
    # Critical fields - required for identification
    'title': 1.0,
    'authors': 1.0,

    # High importance - key metadata
    'series': 0.9,
    'description': 0.9,
    'isbn': 0.8,
    'asin': 0.8,

    # Medium importance - valuable context
    'publication_year': 0.7,
    'narrator': 0.7,
    'publisher': 0.6,

    # Lower importance - nice to have
    'genres': 0.5,
    'subtitle': 0.4,
    'language': 0.4,
    'tags': 0.3,
    'series_sequence': 0.5,
}


def calculate_completeness_score(book: BookMetadata) -> float:
    """
    Calculate weighted completeness score for a book's metadata.

    Scoring logic:
    - Each field contributes its weight if non-empty
    - List fields (authors, genres, tags) count as complete if non-empty
    - Total score = sum(field_weights for complete fields) / sum(all field_weights)

    Args:
        book: BookMetadata instance to score

    Returns:
        float: Completeness score between 0.0 (no metadata) and 1.0 (fully complete)

    Examples:
        >>> book = BookMetadata(id="1", title="Test", authors=["Author"])
        >>> score = calculate_completeness_score(book)
        >>> 0.0 < score < 1.0
        True
    """
    total_weight = sum(FIELD_WEIGHTS.values())
    achieved_weight = 0.0

    for field_name, weight in FIELD_WEIGHTS.items():
        value = getattr(book, field_name, None)

        # Check if field is "complete" (has meaningful value)
        is_complete = False

        if isinstance(value, list):
            # List fields: complete if non-empty
            is_complete = len(value) > 0
        elif isinstance(value, str):
            # String fields: complete if non-empty and not just whitespace
            is_complete = bool(value and value.strip())
        elif value is not None:
            # Other fields: complete if not None
            is_complete = True

        if is_complete:
            achieved_weight += weight

    # Calculate percentage
    if total_weight == 0:
        return 0.0

    score = achieved_weight / total_weight
    return round(score, 4)  # Round to 4 decimal places


def normalize_string(value: str) -> str:
    """
    Normalize string for semantic comparison.

    Removes:
    - Leading/trailing whitespace
    - Multiple consecutive spaces
    - Common punctuation
    - Converts to lowercase

    Args:
        value: String to normalize

    Returns:
        str: Normalized string
    """
    if not value:
        return ""

    # Convert to lowercase
    normalized = value.lower()

    # Remove common punctuation (but keep letters, numbers, spaces)
    normalized = re.sub(r'[^\w\s-]', '', normalized)

    # Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)

    # Strip leading/trailing whitespace
    normalized = normalized.strip()

    return normalized


def extract_year(value: Any) -> Optional[int]:
    """
    Extract year from various date formats.

    Handles:
    - Integer year: 2023
    - ISO date strings: "2023-01-15"
    - Date strings: "January 2023"
    - Datetime objects

    Args:
        value: Value to extract year from

    Returns:
        int or None: Extracted year or None if not found
    """
    if value is None:
        return None

    # Already an integer
    if isinstance(value, int):
        return value if 1000 <= value <= 9999 else None

    # Datetime object
    if isinstance(value, datetime):
        return value.year

    # String - try to extract year
    if isinstance(value, str):
        # Look for 4-digit year
        match = re.search(r'\b(1[0-9]{3}|2[0-9]{3})\b', value)
        if match:
            return int(match.group(1))

    return None


def is_semantically_equivalent(val1: Any, val2: Any, field_type: str = 'string') -> bool:
    """
    Check if two values are semantically equivalent.

    Handles different field types with appropriate comparison logic:
    - Dates: Extracts and compares years
    - Strings: Normalizes whitespace, case, punctuation
    - Author names: Uses fuzzy matching (≥90% similarity = same)
    - Lists: Compares normalized element sets

    Args:
        val1: First value to compare
        val2: Second value to compare
        field_type: Type of field ('string', 'year', 'author', 'list')

    Returns:
        bool: True if values are semantically equivalent

    Examples:
        >>> is_semantically_equivalent("2023", "2023-01-01", field_type='year')
        True
        >>> is_semantically_equivalent(" Title ", "Title", field_type='string')
        True
        >>> is_semantically_equivalent("B. Sanderson", "Brandon Sanderson", field_type='author')
        True (if fuzzy match ≥ 90%)
    """
    # Handle None values
    if val1 is None and val2 is None:
        return True
    if val1 is None or val2 is None:
        return False

    # Year comparison
    if field_type in ('year', 'publication_year'):
        year1 = extract_year(val1)
        year2 = extract_year(val2)
        return year1 == year2 if year1 and year2 else False

    # List comparison (genres, tags, authors when treated as list)
    if field_type == 'list' or isinstance(val1, list) or isinstance(val2, list):
        # Convert to lists if needed
        list1 = val1 if isinstance(val1, list) else [val1]
        list2 = val2 if isinstance(val2, list) else [val2]

        # Normalize and compare as sets (order doesn't matter)
        set1 = {normalize_string(str(item)) for item in list1}
        set2 = {normalize_string(str(item)) for item in list2}

        return set1 == set2

    # Author name comparison (fuzzy matching)
    if field_type in ('author', 'narrator'):
        str1 = normalize_string(str(val1))
        str2 = normalize_string(str(val2))

        # Exact match after normalization
        if str1 == str2:
            return True

        # Fuzzy match using rapidfuzz (≥90% = considered same)
        similarity = fuzz.ratio(str1, str2)
        return similarity >= 90

    # Standard string comparison
    if field_type == 'string' or isinstance(val1, str) or isinstance(val2, str):
        str1 = normalize_string(str(val1))
        str2 = normalize_string(str(val2))
        return str1 == str2

    # Direct comparison for other types
    return val1 == val2


def compare_completeness(book1: BookMetadata, book2: BookMetadata) -> int:
    """
    Compare two books by completeness score.

    Returns:
        int: -1 if book1 < book2, 0 if equal, 1 if book1 > book2
    """
    score1 = book1.completeness_score or calculate_completeness_score(book1)
    score2 = book2.completeness_score or calculate_completeness_score(book2)

    if score1 < score2:
        return -1
    elif score1 > score2:
        return 1
    else:
        return 0


def count_external_identifiers(book: BookMetadata) -> int:
    """
    Count how many external identifiers (ISBN, ASIN) a book has.

    Used as tie-breaker when completeness scores are equal.

    Args:
        book: BookMetadata instance

    Returns:
        int: Number of non-empty external identifiers (0-2)
    """
    count = 0
    if book.isbn and book.isbn.strip():
        count += 1
    if book.asin and book.asin.strip():
        count += 1
    return count


def select_most_complete(books: List[BookMetadata]) -> Optional[BookMetadata]:
    """
    Select the book with the most complete metadata from a list.

    Selection logic:
    1. Highest completeness score wins
    2. If tied, most external identifiers (ISBN/ASIN) wins
    3. If still tied, first book wins

    Args:
        books: List of BookMetadata instances

    Returns:
        BookMetadata or None: Most complete book, or None if list is empty
    """
    if not books:
        return None

    # Sort by completeness (descending), then by identifier count (descending)
    sorted_books = sorted(
        books,
        key=lambda b: (
            b.completeness_score or calculate_completeness_score(b),
            count_external_identifiers(b)
        ),
        reverse=True
    )

    return sorted_books[0]


def format_field_value(value: Any, field_name: str) -> str:
    """
    Format field value for display in reports.

    Args:
        value: Value to format
        field_name: Name of the field

    Returns:
        str: Formatted string representation
    """
    if value is None:
        return "(empty)"

    if isinstance(value, list):
        if not value:
            return "(empty)"
        return ", ".join(str(v) for v in value)

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, (int, float)):
        return str(value)

    return str(value)


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate long strings for display.

    Args:
        text: String to truncate
        max_length: Maximum length before truncation
        suffix: Suffix to add when truncated

    Returns:
        str: Truncated string
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


# Validation helpers
def is_valid_isbn(isbn: Optional[str]) -> bool:
    """Check if ISBN format is valid (basic check)"""
    if not isbn:
        return False
    # Remove hyphens and spaces
    cleaned = re.sub(r'[\s-]', '', isbn)
    # ISBN-10 or ISBN-13
    return bool(re.match(r'^\d{10}$|^\d{13}$', cleaned))


def is_valid_asin(asin: Optional[str]) -> bool:
    """Check if ASIN format is valid (basic check)"""
    if not asin:
        return False
    # ASIN is typically 10 alphanumeric characters
    return bool(re.match(r'^[A-Z0-9]{10}$', asin.upper()))


# Export all functions
__all__ = [
    'FIELD_WEIGHTS',
    'calculate_completeness_score',
    'normalize_string',
    'extract_year',
    'is_semantically_equivalent',
    'compare_completeness',
    'count_external_identifiers',
    'select_most_complete',
    'format_field_value',
    'truncate_string',
    'is_valid_isbn',
    'is_valid_asin',
]
