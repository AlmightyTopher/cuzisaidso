#!/usr/bin/env python3
"""
Metadata Merger for Audiobookshelf Metadata Harmony Agent

Merges metadata across related books based on completeness scores.
Selects authoritative values and applies updates while preserving book-specific data.
"""

from typing import List, Dict, Any, Optional
from copy import deepcopy

from harmony_models import BookMetadata, MetadataDiscrepancy, DiscrepancyType
from harmony_utils import (
    select_most_complete,
    calculate_completeness_score,
    count_external_identifiers,
)


class MetadataMerger:
    """
    Merges metadata across related books using completeness-based selection.

    Key principles:
    - Select most complete metadata as authoritative
    - Preserve book-specific fields (title, description, ISBNs)
    - Apply series-level and author-level harmonization
    - Never destructively overwrite without backup
    """

    # Fields that should never be merged (book-unique)
    PROTECTED_FIELDS = {
        'id',
        'title',
        'subtitle',
        'description',  # Each book has its own synopsis
        'series_sequence',
        'isbn',
        'asin',
        'publication_year',
        'last_modified',
    }

    # Fields that can be harmonized across series
    SERIES_HARMONIZABLE = {
        'series',
        'publisher',
        'genres',
    }

    # Fields that can be harmonized across authors
    AUTHOR_HARMONIZABLE = {
        'authors',
    }

    def __init__(self, dry_run: bool = True):
        """
        Initialize merger.

        Args:
            dry_run: If True, only simulate merges without modifying data
        """
        self.dry_run = dry_run

    def select_authoritative_value(
        self,
        books: List[BookMetadata],
        field_name: str
    ) -> Any:
        """
        Select the most authoritative value for a field across books.

        Selection logic:
        1. Choose value from book with highest completeness score
        2. If tied, prefer book with more external identifiers
        3. If still tied, choose first non-empty value

        Args:
            books: List of books to select from
            field_name: Field to select value for

        Returns:
            The authoritative value for this field
        """
        if field_name in self.PROTECTED_FIELDS:
            # Should never merge protected fields
            return None

        # Filter to books that have this field populated
        books_with_value = []
        for book in books:
            value = getattr(book, field_name, None)
            if self._is_non_empty(value):
                books_with_value.append(book)

        if not books_with_value:
            return None

        # Select most complete book
        most_complete = select_most_complete(books_with_value)

        if most_complete:
            return getattr(most_complete, field_name, None)

        return None

    def merge_by_completeness(
        self,
        books: List[BookMetadata],
        fields: Optional[List[str]] = None
    ) -> Dict[str, BookMetadata]:
        """
        Merge metadata across books, updating all to match most complete values.

        Args:
            books: List of related books to merge
            fields: Optional list of specific fields to merge (default: all harmonizable)

        Returns:
            Dict mapping book_id -> updated BookMetadata
        """
        if len(books) < 2:
            # Nothing to merge
            return {b.id: b for b in books}

        # Determine which fields to merge
        if fields is None:
            fields = list(self.SERIES_HARMONIZABLE | self.AUTHOR_HARMONIZABLE)

        # Create copies to avoid modifying originals
        updated_books = {b.id: deepcopy(b) for b in books}

        # For each field, select authoritative value and apply to all
        for field_name in fields:
            if field_name in self.PROTECTED_FIELDS:
                continue

            authoritative_value = self.select_authoritative_value(books, field_name)

            if authoritative_value is not None:
                # Apply to all books
                for book_id, book in updated_books.items():
                    if not self.dry_run:
                        setattr(book, field_name, authoritative_value)

        # Recalculate completeness scores
        for book in updated_books.values():
            book.completeness_score = calculate_completeness_score(book)

        return updated_books

    def merge_series_metadata(
        self,
        series_books: List[BookMetadata]
    ) -> Dict[str, BookMetadata]:
        """
        Merge series-level metadata (series name, publisher, genres).

        Args:
            series_books: All books in a series

        Returns:
            Dict of updated books
        """
        return self.merge_by_completeness(
            series_books,
            fields=list(self.SERIES_HARMONIZABLE)
        )

    def merge_author_metadata(
        self,
        author_books: List[BookMetadata]
    ) -> Dict[str, BookMetadata]:
        """
        Merge author-level metadata (author names).

        Args:
            author_books: All books by an author

        Returns:
            Dict of updated books
        """
        return self.merge_by_completeness(
            author_books,
            fields=list(self.AUTHOR_HARMONIZABLE)
        )

    def apply_discrepancy_resolution(
        self,
        books: List[BookMetadata],
        discrepancy: MetadataDiscrepancy
    ) -> Dict[str, BookMetadata]:
        """
        Apply resolution for a specific discrepancy.

        Args:
            books: Books affected by discrepancy
            discrepancy: Discrepancy to resolve

        Returns:
            Dict of updated books
        """
        if discrepancy.field_name in self.PROTECTED_FIELDS:
            # Never modify protected fields
            return {b.id: b for b in books}

        if discrepancy.authoritative_value is None:
            # No resolution value
            return {b.id: b for b in books}

        # Create copies
        updated_books = {b.id: deepcopy(b) for b in books}

        # Apply authoritative value to all affected books
        for book_id in discrepancy.affected_book_ids:
            if book_id in updated_books:
                book = updated_books[book_id]

                if not self.dry_run:
                    setattr(book, discrepancy.field_name, discrepancy.authoritative_value)

                # Recalculate completeness
                book.completeness_score = calculate_completeness_score(book)

        return updated_books

    def merge_omnibus_metadata(
        self,
        omnibus: BookMetadata,
        component_books: List[BookMetadata]
    ) -> BookMetadata:
        """
        Merge metadata for omnibus editions.

        Omnibus editions should share series metadata with their components.

        Args:
            omnibus: The omnibus book
            component_books: Individual books contained in omnibus

        Returns:
            Updated omnibus metadata
        """
        # Select authoritative series metadata from components
        all_books = [omnibus] + component_books

        updated = deepcopy(omnibus)

        # Harmonize series-level fields
        for field_name in self.SERIES_HARMONIZABLE:
            if field_name == 'series':
                # Omnibus should share the series name
                authoritative = self.select_authoritative_value(component_books, field_name)
                if authoritative and not self.dry_run:
                    setattr(updated, field_name, authoritative)

            elif field_name == 'publisher':
                # Use most common publisher
                authoritative = self.select_authoritative_value(all_books, field_name)
                if authoritative and not self.dry_run:
                    setattr(updated, field_name, authoritative)

            elif field_name == 'genres':
                # Union of all genres
                all_genres = set()
                for book in all_books:
                    if book.genres:
                        all_genres.update(book.genres)
                if all_genres and not self.dry_run:
                    updated.genres = sorted(list(all_genres))

        # Recalculate completeness
        updated.completeness_score = calculate_completeness_score(updated)

        return updated

    def create_backup(self, books: List[BookMetadata]) -> Dict[str, Dict[str, Any]]:
        """
        Create backup of current metadata state.

        Args:
            books: Books to backup

        Returns:
            Dict mapping book_id -> field_name -> value
        """
        backup = {}

        for book in books:
            book_backup = {}
            for field_name in vars(book):
                if not field_name.startswith('_'):
                    book_backup[field_name] = deepcopy(getattr(book, field_name))
            backup[book.id] = book_backup

        return backup

    def restore_from_backup(
        self,
        books: List[BookMetadata],
        backup: Dict[str, Dict[str, Any]]
    ) -> List[BookMetadata]:
        """
        Restore books from backup.

        Args:
            books: Books to restore
            backup: Backup data from create_backup()

        Returns:
            List of restored books
        """
        restored = []

        for book in books:
            if book.id in backup:
                for field_name, value in backup[book.id].items():
                    if hasattr(book, field_name):
                        setattr(book, field_name, deepcopy(value))
            restored.append(book)

        return restored

    def _is_non_empty(self, value: Any) -> bool:
        """Check if a value is non-empty"""
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, list):
            return len(value) > 0
        return True

    def get_merge_preview(
        self,
        books: List[BookMetadata],
        fields: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Preview what would change in a merge (dry-run).

        Args:
            books: Books to preview merge for
            fields: Optional specific fields

        Returns:
            Dict of book_id -> field_name -> (old_value, new_value)
        """
        # Temporarily enable dry-run
        original_dry_run = self.dry_run
        self.dry_run = True

        preview = {}

        # Perform merge
        merged = self.merge_by_completeness(books, fields)

        # Compare original vs merged
        for book in books:
            if book.id in merged:
                merged_book = merged[book.id]
                changes = {}

                for field_name in vars(book):
                    if field_name.startswith('_'):
                        continue

                    old_value = getattr(book, field_name)
                    new_value = getattr(merged_book, field_name)

                    if old_value != new_value:
                        changes[field_name] = (old_value, new_value)

                if changes:
                    preview[book.id] = changes

        # Restore dry-run setting
        self.dry_run = original_dry_run

        return preview


# Export
__all__ = ['MetadataMerger']
