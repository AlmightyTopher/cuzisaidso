#!/usr/bin/env python3
"""
Metadata Comparator for Audiobookshelf Metadata Harmony Agent

Compares metadata across related books to detect discrepancies.
Uses semantic diff to identify true conflicts (not just formatting differences).

Returns MetadataDiscrepancy objects with confidence scores.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from harmony_models import (
    BookMetadata,
    MetadataDiscrepancy,
    DiscrepancyType,
)
from harmony_utils import (
    is_semantically_equivalent,
    select_most_complete,
    FIELD_WEIGHTS,
)


class MetadataComparator:
    """
    Compares metadata across related books to find inconsistencies.

    Detects:
    - Missing metadata (some books have it, others don't)
    - Conflicting values (semantic differences)
    - Incomplete values (partial vs full information)
    """

    # Fields to compare for series-level harmonization
    SERIES_LEVEL_FIELDS = [
        'series',
        'publisher',
        'genres',
    ]

    # Fields to compare for author-level harmonization
    AUTHOR_LEVEL_FIELDS = [
        'authors',
        'genres',
    ]

    # Fields that should remain book-specific (never harmonized)
    BOOK_SPECIFIC_FIELDS = [
        'id',
        'title',
        'subtitle',
        'description',  # Book-specific synopsis
        'series_sequence',
        'isbn',
        'asin',
        'publication_year',
        'last_modified',
        'completeness_score',
        'related_book_ids',
        'needs_manual_review',
        'last_harmony_check',
    ]

    def __init__(self, confidence_threshold: float = 0.8):
        """
        Initialize comparator.

        Args:
            confidence_threshold: Minimum confidence for auto-resolution
        """
        self.confidence_threshold = confidence_threshold

    def find_discrepancies(
        self,
        book_group: List[BookMetadata],
        fields: Optional[List[str]] = None
    ) -> List[MetadataDiscrepancy]:
        """
        Find metadata discrepancies across a group of related books.

        Args:
            book_group: List of related books to compare
            fields: Optional list of specific fields to check (default: all harmonizable fields)

        Returns:
            List of MetadataDiscrepancy instances
        """
        if len(book_group) < 2:
            return []  # Need at least 2 books to compare

        # Determine which fields to check
        if fields is None:
            fields = self._get_harmonizable_fields()

        discrepancies = []

        for field_name in fields:
            # Skip book-specific fields
            if field_name in self.BOOK_SPECIFIC_FIELDS:
                continue

            # Analyze this field across all books
            field_discrepancy = self._analyze_field(book_group, field_name)

            if field_discrepancy:
                discrepancies.append(field_discrepancy)

        return discrepancies

    def _get_harmonizable_fields(self) -> List[str]:
        """Get list of fields that can be harmonized"""
        # All fields with weights, excluding book-specific ones
        return [
            field for field in FIELD_WEIGHTS.keys()
            if field not in self.BOOK_SPECIFIC_FIELDS
        ]

    def _analyze_field(
        self,
        books: List[BookMetadata],
        field_name: str
    ) -> Optional[MetadataDiscrepancy]:
        """
        Analyze a specific field across books.

        Args:
            books: Books to analyze
            field_name: Name of field to check

        Returns:
            MetadataDiscrepancy if found, None otherwise
        """
        # Collect all values for this field
        values: Dict[str, Any] = {}  # book_id -> value
        non_empty_values: List[Any] = []

        for book in books:
            value = getattr(book, field_name, None)
            values[book.id] = value

            # Track non-empty values
            if self._is_non_empty(value):
                non_empty_values.append(value)

        # Check for missing values
        if len(non_empty_values) < len(books):
            # Some books missing this field
            if len(non_empty_values) == 0:
                # All books missing - not a discrepancy, just incomplete
                return None

            # Partial missing values
            return self._create_missing_discrepancy(books, field_name, values, non_empty_values)

        # Check for conflicting values
        if not self._all_semantically_equivalent(non_empty_values, field_name):
            return self._create_conflicting_discrepancy(books, field_name, values, non_empty_values)

        # No discrepancy found
        return None

    def _is_non_empty(self, value: Any) -> bool:
        """Check if a value is non-empty"""
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, list):
            return len(value) > 0
        return True

    def _all_semantically_equivalent(self, values: List[Any], field_name: str) -> bool:
        """
        Check if all values are semantically equivalent.

        Args:
            values: List of non-empty values
            field_name: Field being compared

        Returns:
            bool: True if all values are semantically the same
        """
        if len(values) <= 1:
            return True

        # Determine field type for semantic comparison
        field_type = self._get_field_type(field_name)

        # Compare all pairs
        first_value = values[0]
        for other_value in values[1:]:
            if not is_semantically_equivalent(first_value, other_value, field_type):
                return False

        return True

    def _get_field_type(self, field_name: str) -> str:
        """Determine field type for semantic comparison"""
        if field_name in ('publication_year',):
            return 'year'
        elif field_name in ('authors', 'narrator'):
            return 'author'
        elif field_name in ('genres', 'tags'):
            return 'list'
        else:
            return 'string'

    def _create_missing_discrepancy(
        self,
        books: List[BookMetadata],
        field_name: str,
        values: Dict[str, Any],
        non_empty_values: List[Any]
    ) -> MetadataDiscrepancy:
        """Create discrepancy for missing values"""
        # Select authoritative value from non-empty ones
        books_with_value = [b for b in books if self._is_non_empty(values[b.id])]
        most_complete = select_most_complete(books_with_value)

        authoritative_value = values[most_complete.id] if most_complete else non_empty_values[0]

        # Calculate confidence based on agreement among non-empty values
        if self._all_semantically_equivalent(non_empty_values, field_name):
            # All non-empty values agree
            confidence = 0.95
            requires_review = False
        else:
            # Non-empty values conflict
            confidence = 0.5
            requires_review = True

        return MetadataDiscrepancy(
            field_name=field_name,
            discrepancy_type=DiscrepancyType.MISSING,
            affected_book_ids=[b.id for b in books],
            conflicting_values=values,
            authoritative_value=authoritative_value,
            confidence=confidence,
            requires_manual_review=requires_review or confidence < self.confidence_threshold,
            detected_at=datetime.now()
        )

    def _create_conflicting_discrepancy(
        self,
        books: List[BookMetadata],
        field_name: str,
        values: Dict[str, Any],
        non_empty_values: List[Any]
    ) -> MetadataDiscrepancy:
        """Create discrepancy for conflicting values"""
        # Select authoritative value based on completeness
        most_complete = select_most_complete(books)
        authoritative_value = values[most_complete.id] if most_complete else non_empty_values[0]

        # Calculate confidence based on how many books agree
        value_counts: Dict[str, int] = {}
        for value in non_empty_values:
            value_str = str(value)
            value_counts[value_str] = value_counts.get(value_str, 0) + 1

        # If majority agrees, higher confidence
        max_count = max(value_counts.values())
        agreement_ratio = max_count / len(non_empty_values)

        # Confidence calculation
        if agreement_ratio >= 0.8:
            confidence = 0.9
            requires_review = False
        elif agreement_ratio >= 0.6:
            confidence = 0.75
            requires_review = True
        else:
            confidence = 0.5
            requires_review = True

        return MetadataDiscrepancy(
            field_name=field_name,
            discrepancy_type=DiscrepancyType.CONFLICTING,
            affected_book_ids=[b.id for b in books],
            conflicting_values=values,
            authoritative_value=authoritative_value,
            confidence=confidence,
            requires_manual_review=requires_review or confidence < self.confidence_threshold,
            detected_at=datetime.now()
        )

    def compare_series_metadata(
        self,
        series_books: List[BookMetadata]
    ) -> List[MetadataDiscrepancy]:
        """
        Compare series-level metadata (fields that should be uniform across series).

        Args:
            series_books: All books in a series

        Returns:
            List of discrepancies in series-level fields
        """
        return self.find_discrepancies(series_books, fields=self.SERIES_LEVEL_FIELDS)

    def compare_author_metadata(
        self,
        author_books: List[BookMetadata]
    ) -> List[MetadataDiscrepancy]:
        """
        Compare author-level metadata (fields that should be consistent per author).

        Args:
            author_books: All books by an author

        Returns:
            List of discrepancies in author-level fields
        """
        return self.find_discrepancies(author_books, fields=self.AUTHOR_LEVEL_FIELDS)

    def prioritize_discrepancies(
        self,
        discrepancies: List[MetadataDiscrepancy]
    ) -> List[MetadataDiscrepancy]:
        """
        Sort discrepancies by priority (critical fields first).

        Priority order:
        1. High-weight fields (title, author, series)
        2. Medium-weight fields (description, publisher)
        3. Low-weight fields (tags, genres)

        Args:
            discrepancies: List of discrepancies to sort

        Returns:
            Sorted list (highest priority first)
        """
        def get_priority(disc: MetadataDiscrepancy) -> float:
            # Higher weight = higher priority
            weight = FIELD_WEIGHTS.get(disc.field_name, 0.0)
            # Conflicting values are more important than missing
            type_bonus = 0.1 if disc.discrepancy_type == DiscrepancyType.CONFLICTING else 0.0
            return weight + type_bonus

        return sorted(discrepancies, key=get_priority, reverse=True)


# Export
__all__ = ['MetadataComparator']
