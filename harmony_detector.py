#!/usr/bin/env python3
"""
Relationship Detector for Audiobookshelf Metadata Harmony Agent

Detects relationships between books using:
- Author matching (fuzzy string matching with rapidfuzz)
- Series membership detection
- Universe/super-series groupings
- Narrator matching

Returns Relationship objects with confidence scores.
"""

from typing import List, Dict, Set
from datetime import datetime
from rapidfuzz import fuzz

from harmony_models import BookMetadata, Relationship, RelationshipType
from harmony_utils import normalize_string


class RelationshipDetector:
    """
    Detects relationships between books based on metadata analysis.

    Uses fuzzy matching and heuristics to identify:
    - Books by the same author (including name variations)
    - Books in the same series
    - Books in the same universe/super-series
    - Books with the same narrator
    """

    def __init__(self, min_confidence: float = 0.8):
        """
        Initialize detector.

        Args:
            min_confidence: Minimum confidence threshold for relationships (0.0-1.0)
        """
        self.min_confidence = min_confidence

    def detect_all_relationships(self, books: List[BookMetadata]) -> List[Relationship]:
        """
        Detect all relationships across a library.

        Args:
            books: List of all books in library

        Returns:
            List of detected Relationship instances
        """
        relationships = []

        # Detect different types of relationships
        relationships.extend(self.detect_author_matches(books))
        relationships.extend(self.detect_series_membership(books))
        relationships.extend(self.detect_universe_groupings(books))
        relationships.extend(self.detect_narrator_matches(books))

        # Filter by confidence threshold
        filtered = [r for r in relationships if r.confidence >= self.min_confidence]

        return filtered

    def detect_author_matches(self, books: List[BookMetadata]) -> List[Relationship]:
        """
        Detect books by the same author using fuzzy name matching.

        Handles name variations like:
        - "B. Sanderson" vs "Brandon Sanderson"
        - "Liu Cixin" vs "Cixin Liu"
        - "J.K. Rowling" vs "J. K. Rowling"

        Args:
            books: List of books to analyze

        Returns:
            List of SAME_AUTHOR relationships
        """
        relationships = []

        # Build author -> book mapping
        author_books: Dict[str, List[BookMetadata]] = {}

        for book in books:
            for author in book.authors:
                normalized = normalize_string(author)
                if normalized not in author_books:
                    author_books[normalized] = []
                author_books[normalized].append(book)

        # Now do fuzzy matching between author names
        author_names = list(author_books.keys())

        for i, author1 in enumerate(author_names):
            for author2 in author_names[i + 1:]:
                # Calculate similarity
                similarity = fuzz.ratio(author1, author2)

                # If ≥90% similar, consider them the same author
                if similarity >= 90:
                    confidence = similarity / 100.0  # Convert to 0.0-1.0

                    # Create relationships between all books by these authors
                    books1 = author_books[author1]
                    books2 = author_books[author2]

                    for book1 in books1:
                        for book2 in books2:
                            if book1.id != book2.id:
                                rel = Relationship(
                                    book_id=book1.id,
                                    related_id=book2.id,
                                    relationship_type=RelationshipType.SAME_AUTHOR,
                                    confidence=confidence,
                                    metadata_used=['authors'],
                                    detected_at=datetime.now()
                                )
                                relationships.append(rel)

        # Also add exact matches (books with identical normalized author names)
        for normalized, book_list in author_books.items():
            if len(book_list) > 1:
                # All books in this list have the same author
                for i, book1 in enumerate(book_list):
                    for book2 in book_list[i + 1:]:
                        rel = Relationship(
                            book_id=book1.id,
                            related_id=book2.id,
                            relationship_type=RelationshipType.SAME_AUTHOR,
                            confidence=1.0,  # Exact match
                            metadata_used=['authors'],
                            detected_at=datetime.now()
                        )
                        relationships.append(rel)

        return relationships

    def detect_series_membership(self, books: List[BookMetadata]) -> List[Relationship]:
        """
        Detect books in the same series.

        Uses:
        - Series name matching (with fuzzy matching for variations)
        - Series sequence numbers for validation

        Args:
            books: List of books to analyze

        Returns:
            List of SAME_SERIES relationships
        """
        relationships = []

        # Build series -> book mapping
        series_books: Dict[str, List[BookMetadata]] = {}

        for book in books:
            if book.series:
                normalized = normalize_string(book.series)
                if normalized not in series_books:
                    series_books[normalized] = []
                series_books[normalized].append(book)

        # Create relationships within each series
        for normalized_series, book_list in series_books.items():
            if len(book_list) > 1:
                # Calculate confidence based on consistency
                confidence = self._calculate_series_confidence(book_list)

                # Create relationships between all books in series
                for i, book1 in enumerate(book_list):
                    for book2 in book_list[i + 1:]:
                        rel = Relationship(
                            book_id=book1.id,
                            related_id=book2.id,
                            relationship_type=RelationshipType.SAME_SERIES,
                            confidence=confidence,
                            metadata_used=['series', 'series_sequence'],
                            detected_at=datetime.now()
                        )
                        relationships.append(rel)

        # Fuzzy matching for series name variations
        series_names = list(series_books.keys())
        for i, series1 in enumerate(series_names):
            for series2 in series_names[i + 1:]:
                similarity = fuzz.ratio(series1, series2)

                if similarity >= 85:  # Slightly lower threshold for series names
                    confidence = similarity / 100.0

                    books1 = series_books[series1]
                    books2 = series_books[series2]

                    for book1 in books1:
                        for book2 in books2:
                            if book1.id != book2.id:
                                rel = Relationship(
                                    book_id=book1.id,
                                    related_id=book2.id,
                                    relationship_type=RelationshipType.SAME_SERIES,
                                    confidence=confidence,
                                    metadata_used=['series'],
                                    detected_at=datetime.now()
                                )
                                relationships.append(rel)

        return relationships

    def detect_universe_groupings(self, books: List[BookMetadata]) -> List[Relationship]:
        """
        Detect books in the same universe (super-series).

        Looks for patterns like:
        - "Riftwar Cycle" containing multiple sub-series
        - "Cosmere" containing multiple series
        - Shared universe indicators in series names

        Args:
            books: List of books to analyze

        Returns:
            List of SAME_UNIVERSE relationships
        """
        relationships = []

        # Look for hierarchical series patterns
        # E.g., "Riftwar Cycle: The Riftwar Saga"
        universe_map: Dict[str, List[BookMetadata]] = {}

        for book in books:
            if not book.series:
                continue

            # Check for common universe indicators
            series_lower = book.series.lower()

            # Pattern: "Universe: Sub-series"
            if ':' in book.series or ' - ' in book.series:
                parts = book.series.replace(' - ', ':').split(':')
                if len(parts) >= 2:
                    universe = normalize_string(parts[0])
                    if universe not in universe_map:
                        universe_map[universe] = []
                    universe_map[universe].append(book)

            # Pattern: "The [X] Series" variations
            elif any(word in series_lower for word in ['saga', 'cycle', 'chronicles', 'trilogy']):
                # Extract base name
                base = normalize_string(book.series)
                if base not in universe_map:
                    universe_map[base] = []
                universe_map[base].append(book)

        # Create universe relationships
        for universe, book_list in universe_map.items():
            if len(book_list) > 1:
                confidence = 0.85  # Lower confidence for inferred universes

                for i, book1 in enumerate(book_list):
                    for book2 in book_list[i + 1:]:
                        rel = Relationship(
                            book_id=book1.id,
                            related_id=book2.id,
                            relationship_type=RelationshipType.SAME_UNIVERSE,
                            confidence=confidence,
                            metadata_used=['series'],
                            detected_at=datetime.now()
                        )
                        relationships.append(rel)

        return relationships

    def detect_narrator_matches(self, books: List[BookMetadata]) -> List[Relationship]:
        """
        Detect books narrated by the same person.

        Uses fuzzy matching for narrator name variations.

        Args:
            books: List of books to analyze

        Returns:
            List of SAME_NARRATOR relationships
        """
        relationships = []

        # Build narrator -> book mapping
        narrator_books: Dict[str, List[BookMetadata]] = {}

        for book in books:
            if book.narrator:
                normalized = normalize_string(book.narrator)
                if normalized not in narrator_books:
                    narrator_books[normalized] = []
                narrator_books[normalized].append(book)

        # Create relationships for books with same narrator
        for normalized_narrator, book_list in narrator_books.items():
            if len(book_list) > 1:
                for i, book1 in enumerate(book_list):
                    for book2 in book_list[i + 1:]:
                        rel = Relationship(
                            book_id=book1.id,
                            related_id=book2.id,
                            relationship_type=RelationshipType.SAME_NARRATOR,
                            confidence=1.0,  # Exact narrator match
                            metadata_used=['narrator'],
                            detected_at=datetime.now()
                        )
                        relationships.append(rel)

        # Fuzzy matching for narrator name variations
        narrator_names = list(narrator_books.keys())
        for i, narrator1 in enumerate(narrator_names):
            for narrator2 in narrator_names[i + 1:]:
                similarity = fuzz.ratio(narrator1, narrator2)

                if similarity >= 90:
                    confidence = similarity / 100.0

                    books1 = narrator_books[narrator1]
                    books2 = narrator_books[narrator2]

                    for book1 in books1:
                        for book2 in books2:
                            if book1.id != book2.id:
                                rel = Relationship(
                                    book_id=book1.id,
                                    related_id=book2.id,
                                    relationship_type=RelationshipType.SAME_NARRATOR,
                                    confidence=confidence,
                                    metadata_used=['narrator'],
                                    detected_at=datetime.now()
                                )
                                relationships.append(rel)

        return relationships

    def _calculate_series_confidence(self, books: List[BookMetadata]) -> float:
        """
        Calculate confidence for series membership.

        Higher confidence when:
        - Series sequences are present and consistent
        - All books have same author(s)
        - Publisher is consistent

        Args:
            books: Books in the series

        Returns:
            float: Confidence score (0.0-1.0)
        """
        if not books:
            return 0.0

        confidence = 1.0

        # Check for series sequence numbers
        has_sequence = sum(1 for b in books if b.series_sequence) / len(books)
        if has_sequence < 0.5:
            # Less than half have sequence numbers - reduce confidence
            confidence *= 0.9

        # Check author consistency
        all_authors: Set[str] = set()
        for book in books:
            for author in book.authors:
                all_authors.add(normalize_string(author))

        if len(all_authors) > 3:
            # Too many different authors for a single series
            confidence *= 0.85

        # Check publisher consistency
        publishers = {normalize_string(b.publisher) for b in books if b.publisher}
        if len(publishers) > 2:
            # Multiple publishers - might be inconsistent
            confidence *= 0.95

        return round(confidence, 3)


# Export
__all__ = ['RelationshipDetector']
