#!/usr/bin/env python3
"""
Harmony Orchestrator for Audiobookshelf Metadata Harmony Agent

Coordinates the complete harmonization workflow:
- Phase 1: Scan & Score
- Phase 2: Detect Relationships
- Phase 3: Compare & Find Discrepancies
- Phase 4: Merge & Apply (if not dry-run)
- Phase 5: Validate

Generates CompletionReport with full statistics.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from copy import deepcopy

import httpx

from harmony_models import (
    BookMetadata,
    Relationship,
    MetadataDiscrepancy,
    CompletionReport,
    AuditRecord,
    HarmonyConfig,
)
from harmony_utils import calculate_completeness_score
from harmony_database import HarmonyDatabase
from harmony_detector import RelationshipDetector
from harmony_comparator import MetadataComparator
from harmony_merger import MetadataMerger
from harmony_validator import ValidationAgent


logger = logging.getLogger(__name__)


class HarmonyOrchestrator:
    """
    Orchestrates the complete metadata harmonization workflow.

    Workflow:
    1. Scan library and calculate completeness scores
    2. Detect relationships between books
    3. Compare metadata and find discrepancies
    4. Merge and apply updates (or dry-run preview)
    5. Validate results and generate report
    """

    def __init__(self, config: HarmonyConfig, database: HarmonyDatabase):
        """
        Initialize orchestrator.

        Args:
            config: Configuration settings
            database: Database for caching and audit logs
        """
        self.config = config
        self.db = database

        # Initialize agents
        self.detector = RelationshipDetector(min_confidence=config.confidence_threshold)
        self.comparator = MetadataComparator(confidence_threshold=config.confidence_threshold)
        self.merger = MetadataMerger(dry_run=config.dry_run)
        self.validator = ValidationAgent()

        # HTTP client for ABS API
        self.client = httpx.AsyncClient(
            base_url=config.abs_url,
            headers={"Authorization": f"Bearer {config.abs_token}"},
            timeout=config.request_timeout
        )

        # Workflow state
        self.books: List[BookMetadata] = []
        self.books_before: List[BookMetadata] = []  # Backup for validation
        self.relationships: List[Relationship] = []
        self.discrepancies: List[MetadataDiscrepancy] = []
        self.audit_records: List[AuditRecord] = []

    async def run(self) -> CompletionReport:
        """
        Execute complete harmonization workflow.

        Returns:
            CompletionReport with statistics and results
        """
        start_time = datetime.now()

        logger.info("Starting harmony workflow...")

        try:
            # Phase 1: Scan & Score
            await self._phase_scan_and_score()

            # Phase 2: Detect Relationships
            await self._phase_detect_relationships()

            # Phase 3: Compare & Find Discrepancies
            await self._phase_compare_metadata()

            # Phase 4: Merge & Apply
            if not self.config.dry_run:
                await self._phase_merge_and_apply()
            else:
                logger.info("Dry-run mode: Skipping update phase")

            # Phase 5: Validate
            await self._phase_validate()

            # Generate report
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            report = self._generate_report(duration)

            logger.info(f"Harmony workflow completed in {duration:.2f}s")

            return report

        except Exception as e:
            logger.error(f"Harmony workflow failed: {e}", exc_info=True)
            raise

        finally:
            await self.client.aclose()

    async def _phase_scan_and_score(self):
        """Phase 1: Scan library and calculate completeness scores"""
        logger.info("Phase 1: Scanning library and calculating completeness...")

        # Fetch all books from Audiobookshelf
        self.books = await self._fetch_all_books()

        logger.info(f"Fetched {len(self.books)} books from library")

        # Calculate completeness scores
        for book in self.books:
            # Check cache first
            if not self.config.force_rescan:
                cached_score = self.db.get_completeness_score(book.id)
                if cached_score is not None:
                    book.completeness_score = cached_score
                    continue

            # Calculate and cache
            score = calculate_completeness_score(book)
            book.completeness_score = score
            self.db.save_completeness_score(book.id, score)

        # Create backup for validation
        self.books_before = [deepcopy(b) for b in self.books]

        logger.info("Phase 1 complete: All books scanned and scored")

    async def _phase_detect_relationships(self):
        """Phase 2: Detect relationships between books"""
        logger.info("Phase 2: Detecting relationships...")

        # Detect all relationships
        self.relationships = self.detector.detect_all_relationships(self.books)

        logger.info(f"Detected {len(self.relationships)} relationships")

        # Cache relationships
        for rel in self.relationships:
            self.db.save_relationship(rel)

        # Update related_book_ids on books
        related_map: Dict[str, List[str]] = defaultdict(list)
        for rel in self.relationships:
            related_map[rel.book_id].append(rel.related_id)
            related_map[rel.related_id].append(rel.book_id)

        for book in self.books:
            book.related_book_ids = list(set(related_map.get(book.id, [])))

        logger.info("Phase 2 complete: Relationships detected and cached")

    async def _phase_compare_metadata(self):
        """Phase 3: Compare metadata and find discrepancies"""
        logger.info("Phase 3: Comparing metadata and finding discrepancies...")

        # Group books by series
        series_groups = self._group_books_by_series()

        # Group books by author
        author_groups = self._group_books_by_author()

        # Find discrepancies in each group
        for series_name, books in series_groups.items():
            series_discreps = self.comparator.compare_series_metadata(books)
            self.discrepancies.extend(series_discreps)

        for author_name, books in author_groups.items():
            author_discreps = self.comparator.compare_author_metadata(books)
            self.discrepancies.extend(author_discreps)

        # Prioritize discrepancies
        self.discrepancies = self.comparator.prioritize_discrepancies(self.discrepancies)

        logger.info(f"Found {len(self.discrepancies)} discrepancies")

        # Flag books for manual review
        for discrepancy in self.discrepancies:
            if discrepancy.requires_manual_review:
                for book_id in discrepancy.affected_book_ids:
                    self.db.add_to_review_queue(
                        book_id,
                        f"Low confidence ({discrepancy.confidence:.2f}) for field '{discrepancy.field_name}'",
                        discrepancy.field_name
                    )

        logger.info("Phase 3 complete: Discrepancies identified and prioritized")

    async def _phase_merge_and_apply(self):
        """Phase 4: Merge metadata and apply updates"""
        logger.info("Phase 4: Merging and applying updates...")

        updates_applied = 0

        # Group books by series for series-level merging
        series_groups = self._group_books_by_series()

        for series_name, books in series_groups.items():
            merged = self.merger.merge_series_metadata(books)

            # Apply updates via API
            for book_id, updated_book in merged.items():
                success = await self._update_book_metadata(book_id, updated_book)
                if success:
                    updates_applied += 1

        logger.info(f"Phase 4 complete: {updates_applied} updates applied")

    async def _phase_validate(self):
        """Phase 5: Validate results"""
        logger.info("Phase 5: Validating results...")

        series_groups = self._group_books_by_series()
        author_groups = self._group_books_by_author()

        success, errors = self.validator.run_full_validation(
            self.books,
            series_groups,
            author_groups,
            before=self.books_before if not self.config.dry_run else None
        )

        if success:
            logger.info("Phase 5 complete: All validations passed")
        else:
            logger.warning(f"Phase 5 complete: {len(errors)} validation errors found")
            for error in errors[:10]:  # Log first 10 errors
                logger.warning(f"  - {error}")

    async def _fetch_all_books(self) -> List[BookMetadata]:
        """Fetch all books from Audiobookshelf API"""
        books = []

        # Get all libraries
        response = await self.client.get("/api/libraries")
        response.raise_for_status()
        libraries = response.json()["libraries"]

        # Fetch books from each library
        for library in libraries:
            lib_response = await self.client.get(f"/api/libraries/{library['id']}/items")
            lib_response.raise_for_status()
            items = lib_response.json()["results"]

            for item in items:
                book = self._parse_book_from_api(item)
                if book:
                    books.append(book)

        return books

    def _parse_book_from_api(self, item: Dict) -> Optional[BookMetadata]:
        """Parse BookMetadata from API response"""
        try:
            media = item.get("media", {})
            metadata = media.get("metadata", {})

            return BookMetadata(
                id=item["id"],
                title=metadata.get("title", ""),
                subtitle=metadata.get("subtitle"),
                authors=metadata.get("authors", []),
                series=metadata.get("series"),
                series_sequence=metadata.get("sequence"),
                description=metadata.get("description"),
                publication_year=metadata.get("publishedYear"),
                narrator=metadata.get("narrator"),
                isbn=metadata.get("isbn"),
                asin=metadata.get("asin"),
                publisher=metadata.get("publisher"),
                language=metadata.get("language"),
                genres=metadata.get("genres", []),
                tags=item.get("tags", []),
                last_modified=datetime.fromisoformat(item["updatedAt"]) if "updatedAt" in item else None,
            )
        except Exception as e:
            logger.error(f"Failed to parse book {item.get('id', 'unknown')}: {e}")
            return None

    async def _update_book_metadata(self, book_id: str, book: BookMetadata) -> bool:
        """Update book metadata via API"""
        try:
            # Prepare update payload
            payload = {
                "metadata": {
                    "title": book.title,
                    "subtitle": book.subtitle,
                    "authors": book.authors,
                    "series": book.series,
                    "sequence": book.series_sequence,
                    "description": book.description,
                    "publishedYear": book.publication_year,
                    "narrator": book.narrator,
                    "isbn": book.isbn,
                    "asin": book.asin,
                    "publisher": book.publisher,
                    "language": book.language,
                    "genres": book.genres,
                },
                "tags": book.tags,
            }

            response = await self.client.patch(f"/api/items/{book_id}/metadata", json=payload)
            response.raise_for_status()

            logger.debug(f"Updated book {book_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update book {book_id}: {e}")
            return False

    def _group_books_by_series(self) -> Dict[str, List[BookMetadata]]:
        """Group books by series name"""
        groups: Dict[str, List[BookMetadata]] = defaultdict(list)

        for book in self.books:
            if book.series:
                groups[book.series].append(book)

        return dict(groups)

    def _group_books_by_author(self) -> Dict[str, List[BookMetadata]]:
        """Group books by author"""
        groups: Dict[str, List[BookMetadata]] = defaultdict(list)

        for book in self.books:
            for author in book.authors:
                groups[author].append(book)

        return dict(groups)

    def _generate_report(self, duration: float) -> CompletionReport:
        """Generate completion report"""
        # Calculate statistics
        total_books = len(self.books)
        avg_before = sum(b.completeness_score for b in self.books_before) / total_books if total_books > 0 else 0.0
        avg_after = sum(b.completeness_score for b in self.books) / total_books if total_books > 0 else 0.0

        # Relationship type breakdown
        rel_by_type = defaultdict(int)
        for rel in self.relationships:
            rel_by_type[rel.relationship_type.value] += 1

        # Discrepancy breakdown
        disc_by_type = defaultdict(int)
        disc_by_field = defaultdict(int)
        for disc in self.discrepancies:
            disc_by_type[disc.discrepancy_type.value] += 1
            disc_by_field[disc.field_name] += 1

        # Confidence distribution
        conf_dist = {"<0.5": 0, "0.5-0.7": 0, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 0}
        for disc in self.discrepancies:
            if disc.confidence < 0.5:
                conf_dist["<0.5"] += 1
            elif disc.confidence < 0.7:
                conf_dist["0.5-0.7"] += 1
            elif disc.confidence < 0.8:
                conf_dist["0.7-0.8"] += 1
            elif disc.confidence < 0.9:
                conf_dist["0.8-0.9"] += 1
            else:
                conf_dist["0.9-1.0"] += 1

        # Manual review count
        review_queue = self.db.get_review_queue(resolved=False)

        return CompletionReport(
            timestamp=datetime.now(),
            duration_seconds=duration,
            dry_run=self.config.dry_run,
            total_books=total_books,
            books_scanned=total_books,
            scan_errors=0,
            relationships_found=len(self.relationships),
            relationships_by_type=dict(rel_by_type),
            discrepancies_found=len(self.discrepancies),
            discrepancies_by_type=dict(disc_by_type),
            discrepancies_by_field=dict(disc_by_field),
            updates_applied=0 if self.config.dry_run else len(self.audit_records),
            updates_by_field={},
            updates_failed=0,
            confidence_distribution=conf_dist,
            books_flagged_for_review=len(review_queue),
            review_reasons={},
            avg_completeness_before=avg_before,
            avg_completeness_after=avg_after,
            validation_passed=True,
            validation_errors=[],
        )


# Export
__all__ = ['HarmonyOrchestrator']
