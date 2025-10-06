#!/usr/bin/env python3
"""
Validation Agent for Audiobookshelf Metadata Harmony Agent

Verifies metadata consistency post-update to ensure harmonization was successful.
Checks series consistency, author consistency, and data integrity.
"""

from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict

from harmony_models import BookMetadata
from harmony_utils import is_semantically_equivalent, normalize_string


class ValidationAgent:
    """
    Validates metadata consistency after harmonization.

    Performs:
    - Series consistency checks (all books in series have uniform metadata)
    - Author consistency checks (author names are uniform)
    - Data integrity checks (no corrupted or invalid values)
    - Completeness verification (scores increased, not decreased)
    """

    def __init__(self):
        """Initialize validator"""
        self.errors: List[str] = []

    def verify_series_consistency(
        self,
        series_name: str,
        books: List[BookMetadata]
    ) -> Tuple[bool, List[str]]:
        """
        Verify that all books in a series have consistent metadata.

        Checks:
        - All books have same series name
        - Publisher is consistent
        - Genres are reasonably aligned
        - No sequence number conflicts

        Args:
            series_name: Name of the series
            books: Books claimed to be in this series

        Returns:
            Tuple of (success: bool, errors: List[str])
        """
        errors = []

        if len(books) < 2:
            return True, []  # Single book, nothing to validate

        # Check series name consistency
        series_names = set()
        for book in books:
            if book.series:
                series_names.add(normalize_string(book.series))

        if len(series_names) > 1:
            errors.append(
                f"Series '{series_name}': Inconsistent series names found: {series_names}"
            )

        # Check for duplicate sequence numbers
        sequences: Dict[str, List[str]] = defaultdict(list)  # sequence -> book_ids
        for book in books:
            if book.series_sequence:
                sequences[book.series_sequence].append(book.id)

        for sequence, book_ids in sequences.items():
            if len(book_ids) > 1:
                errors.append(
                    f"Series '{series_name}': Duplicate sequence number {sequence} "
                    f"for books: {book_ids}"
                )

        # Check publisher consistency (should be mostly the same)
        publishers = [normalize_string(b.publisher) for b in books if b.publisher]
        if publishers:
            publisher_counts = {}
            for pub in publishers:
                publisher_counts[pub] = publisher_counts.get(pub, 0) + 1

            most_common_count = max(publisher_counts.values())
            if most_common_count / len(publishers) < 0.7:
                errors.append(
                    f"Series '{series_name}': Low publisher consistency "
                    f"({most_common_count}/{len(publishers)} books)"
                )

        # Check genre consistency (at least 50% overlap expected)
        if len(books) > 1:
            all_genres: List[Set[str]] = []
            for book in books:
                if book.genres:
                    all_genres.append(set(normalize_string(g) for g in book.genres))

            if len(all_genres) >= 2:
                # Calculate average overlap
                overlaps = []
                for i in range(len(all_genres)):
                    for j in range(i + 1, len(all_genres)):
                        if all_genres[i] or all_genres[j]:
                            union = all_genres[i] | all_genres[j]
                            intersection = all_genres[i] & all_genres[j]
                            overlap = len(intersection) / len(union) if union else 0
                            overlaps.append(overlap)

                if overlaps:
                    avg_overlap = sum(overlaps) / len(overlaps)
                    if avg_overlap < 0.3:
                        errors.append(
                            f"Series '{series_name}': Low genre consistency "
                            f"(avg overlap: {avg_overlap:.1%})"
                        )

        return len(errors) == 0, errors

    def verify_author_consistency(
        self,
        author_name: str,
        books: List[BookMetadata]
    ) -> Tuple[bool, List[str]]:
        """
        Verify that all books by an author have consistent author metadata.

        Checks:
        - Author name is consistent across books
        - No unexpected author variations remain

        Args:
            author_name: Canonical author name
            books: Books by this author

        Returns:
            Tuple of (success: bool, errors: List[str])
        """
        errors = []

        if len(books) < 2:
            return True, []

        # Check for author name consistency
        author_variations: Set[str] = set()

        for book in books:
            for author in book.authors:
                normalized = normalize_string(author)
                author_variations.add(normalized)

        # All should be semantically equivalent to the canonical name
        canonical_normalized = normalize_string(author_name)

        inconsistent = []
        for variation in author_variations:
            if not is_semantically_equivalent(variation, canonical_normalized, 'author'):
                inconsistent.append(variation)

        if inconsistent:
            errors.append(
                f"Author '{author_name}': Inconsistent author names found: {inconsistent}"
            )

        return len(errors) == 0, errors

    def verify_completeness_improvement(
        self,
        before: List[BookMetadata],
        after: List[BookMetadata]
    ) -> Tuple[bool, List[str]]:
        """
        Verify that harmonization improved (or maintained) completeness scores.

        Args:
            before: Books before harmonization
            after: Books after harmonization

        Returns:
            Tuple of (success: bool, errors: List[str])
        """
        errors = []

        # Create mapping by ID
        before_map = {b.id: b for b in before}
        after_map = {b.id: b for b in after}

        decreased = []

        for book_id in before_map:
            if book_id in after_map:
                score_before = before_map[book_id].completeness_score
                score_after = after_map[book_id].completeness_score

                # Allow small floating point differences
                if score_after < score_before - 0.001:
                    decreased.append(
                        f"Book {book_id}: completeness decreased "
                        f"from {score_before:.3f} to {score_after:.3f}"
                    )

        if decreased:
            errors.append(
                f"Completeness decreased for {len(decreased)} books: {decreased[:3]}"
            )

        return len(errors) == 0, errors

    def verify_no_data_loss(
        self,
        before: List[BookMetadata],
        after: List[BookMetadata],
        protected_fields: Set[str]
    ) -> Tuple[bool, List[str]]:
        """
        Verify that protected fields were not modified.

        Args:
            before: Books before harmonization
            after: Books after harmonization
            protected_fields: Set of field names that should never change

        Returns:
            Tuple of (success: bool, errors: List[str])
        """
        errors = []

        before_map = {b.id: b for b in before}
        after_map = {b.id: b for b in after}

        for book_id in before_map:
            if book_id not in after_map:
                errors.append(f"Book {book_id} was deleted during harmonization")
                continue

            book_before = before_map[book_id]
            book_after = after_map[book_id]

            for field_name in protected_fields:
                value_before = getattr(book_before, field_name, None)
                value_after = getattr(book_after, field_name, None)

                if value_before != value_after:
                    errors.append(
                        f"Book {book_id}: Protected field '{field_name}' was modified "
                        f"from '{value_before}' to '{value_after}'"
                    )

        return len(errors) == 0, errors

    def verify_relationships_valid(
        self,
        books: List[BookMetadata]
    ) -> Tuple[bool, List[str]]:
        """
        Verify that relationship IDs are valid.

        Checks that all related_book_ids actually exist in the library.

        Args:
            books: All books in library

        Returns:
            Tuple of (success: bool, errors: List[str])
        """
        errors = []

        valid_ids = {b.id for b in books}

        for book in books:
            for related_id in book.related_book_ids:
                if related_id not in valid_ids:
                    errors.append(
                        f"Book {book.id} references non-existent book: {related_id}"
                    )

        return len(errors) == 0, errors

    def validate_book_data(self, book: BookMetadata) -> Tuple[bool, List[str]]:
        """
        Validate individual book data integrity.

        Checks:
        - Required fields are present
        - Data types are correct
        - Values are within valid ranges

        Args:
            book: Book to validate

        Returns:
            Tuple of (success: bool, errors: List[str])
        """
        errors = []

        # Required fields
        if not book.id:
            errors.append("Book missing ID")
        if not book.title or not book.title.strip():
            errors.append(f"Book {book.id} missing title")

        # Completeness score range
        if not 0.0 <= book.completeness_score <= 1.0:
            errors.append(
                f"Book {book.id} has invalid completeness score: {book.completeness_score}"
            )

        # Publication year range
        if book.publication_year:
            if book.publication_year < 1000 or book.publication_year > 2100:
                errors.append(
                    f"Book {book.id} has invalid publication year: {book.publication_year}"
                )

        # Series sequence should be numeric-ish
        if book.series_sequence:
            try:
                float(book.series_sequence.replace(',', '.'))
            except ValueError:
                # Not a number - could be "Book 1" or "Part One" - that's okay
                pass

        # Authors list should not be empty if present
        if book.authors is not None and not book.authors:
            errors.append(f"Book {book.id} has empty authors list")

        return len(errors) == 0, errors

    def run_full_validation(
        self,
        books: List[BookMetadata],
        series_groups: Dict[str, List[BookMetadata]],
        author_groups: Dict[str, List[BookMetadata]],
        before: Optional[List[BookMetadata]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Run complete validation suite.

        Args:
            books: All books after harmonization
            series_groups: Books grouped by series
            author_groups: Books grouped by author
            before: Optional books before harmonization (for comparison)

        Returns:
            Tuple of (all_passed: bool, all_errors: List[str])
        """
        all_errors = []

        # Validate each book individually
        for book in books:
            success, errors = self.validate_book_data(book)
            if not success:
                all_errors.extend(errors)

        # Validate series consistency
        for series_name, series_books in series_groups.items():
            success, errors = self.verify_series_consistency(series_name, series_books)
            if not success:
                all_errors.extend(errors)

        # Validate author consistency
        for author_name, author_books in author_groups.items():
            success, errors = self.verify_author_consistency(author_name, author_books)
            if not success:
                all_errors.extend(errors)

        # Validate relationships
        success, errors = self.verify_relationships_valid(books)
        if not success:
            all_errors.extend(errors)

        # If before data available, validate improvements
        if before:
            success, errors = self.verify_completeness_improvement(before, books)
            if not success:
                all_errors.extend(errors)

            protected = {'id', 'title', 'subtitle', 'isbn', 'asin'}
            success, errors = self.verify_no_data_loss(before, books, protected)
            if not success:
                all_errors.extend(errors)

        return len(all_errors) == 0, all_errors


# Export
__all__ = ['ValidationAgent']
