#!/usr/bin/env python3
"""
Pydantic data models for Audiobookshelf Metadata Harmony Agent

Defines data structures for:
- BookMetadata (with completeness_score, related_book_ids, needs_manual_review)
- Relationship
- MetadataDiscrepancy
- CompletionReport
- AuditRecord
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class RelationshipType(str, Enum):
    """Types of relationships between books"""
    SAME_AUTHOR = "same_author"
    SAME_SERIES = "same_series"
    SAME_UNIVERSE = "same_universe"
    SAME_NARRATOR = "same_narrator"
    RELATED_WORK = "related_work"


class DiscrepancyType(str, Enum):
    """Types of metadata discrepancies"""
    MISSING = "missing"
    CONFLICTING = "conflicting"
    INCOMPLETE = "incomplete"


class BookMetadata(BaseModel):
    """Extended book metadata with harmony-specific fields"""
    model_config = ConfigDict(extra='allow')

    # Core metadata (from Audiobookshelf)
    id: str = Field(..., description="Book ID from Audiobookshelf")
    title: str = Field(..., description="Book title")
    subtitle: Optional[str] = Field(None, description="Book subtitle")
    authors: List[str] = Field(default_factory=list, description="List of author names")
    series: Optional[str] = Field(None, description="Series name")
    series_sequence: Optional[str] = Field(None, description="Position in series")
    description: Optional[str] = Field(None, description="Book description/synopsis")
    publication_year: Optional[int] = Field(None, description="Year of publication")
    narrator: Optional[str] = Field(None, description="Narrator name")
    isbn: Optional[str] = Field(None, description="ISBN identifier")
    asin: Optional[str] = Field(None, description="ASIN identifier")
    publisher: Optional[str] = Field(None, description="Publisher name")
    language: Optional[str] = Field(None, description="Book language")
    genres: List[str] = Field(default_factory=list, description="Genre tags")
    tags: List[str] = Field(default_factory=list, description="User tags")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")

    # Harmony-specific fields
    completeness_score: float = Field(0.0, ge=0.0, le=1.0, description="Metadata completeness (0.0-1.0)")
    related_book_ids: List[str] = Field(default_factory=list, description="IDs of related books")
    needs_manual_review: bool = Field(False, description="Flagged for manual review")
    last_harmony_check: Optional[datetime] = Field(None, description="Last harmony scan timestamp")

    @field_validator('publication_year')
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        """Validate publication year is reasonable"""
        if v is not None and (v < 1000 or v > datetime.now().year + 2):
            raise ValueError(f"Publication year {v} is out of valid range")
        return v

    @field_validator('completeness_score')
    @classmethod
    def validate_completeness(cls, v: float) -> float:
        """Ensure completeness score is in valid range"""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Completeness score must be between 0.0 and 1.0, got {v}")
        return v


class Relationship(BaseModel):
    """Represents a detected relationship between books"""
    model_config = ConfigDict(extra='forbid')

    book_id: str = Field(..., description="Source book ID")
    related_id: str = Field(..., description="Related book ID")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    metadata_used: List[str] = Field(default_factory=list, description="Fields used for detection")
    detected_at: datetime = Field(default_factory=datetime.now, description="Detection timestamp")

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is in valid range"""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator('book_id', 'related_id')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure IDs are not empty"""
        if not v or not v.strip():
            raise ValueError("Book IDs cannot be empty")
        return v


class MetadataDiscrepancy(BaseModel):
    """Represents a detected metadata inconsistency"""
    model_config = ConfigDict(extra='forbid')

    field_name: str = Field(..., description="Metadata field with discrepancy")
    discrepancy_type: DiscrepancyType = Field(..., description="Type of discrepancy")
    affected_book_ids: List[str] = Field(..., description="Books involved in discrepancy")
    conflicting_values: Dict[str, Any] = Field(default_factory=dict, description="book_id -> value mapping")
    authoritative_value: Optional[Any] = Field(None, description="Proposed resolution value")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Resolution confidence")
    requires_manual_review: bool = Field(False, description="Needs human decision")
    detected_at: datetime = Field(default_factory=datetime.now, description="Detection timestamp")

    @field_validator('affected_book_ids')
    @classmethod
    def validate_affected_books(cls, v: List[str]) -> List[str]:
        """Ensure at least one book is affected"""
        if not v:
            raise ValueError("At least one affected book ID is required")
        return v


class AuditRecord(BaseModel):
    """Historical log entry for metadata changes"""
    model_config = ConfigDict(extra='forbid')

    timestamp: datetime = Field(default_factory=datetime.now, description="When change occurred")
    book_id: str = Field(..., description="Book that was modified")
    field: str = Field(..., description="Metadata field changed")
    old_value: Optional[Any] = Field(None, description="Previous value")
    new_value: Optional[Any] = Field(None, description="New value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in change")
    data_source: str = Field("harmony_agent", description="Source of change")
    success: bool = Field(True, description="Whether change was applied successfully")
    error_message: Optional[str] = Field(None, description="Error details if failed")


class CompletionReport(BaseModel):
    """Summary report of harmony operation"""
    model_config = ConfigDict(extra='forbid')

    # Execution metadata
    timestamp: datetime = Field(default_factory=datetime.now, description="Report generation time")
    duration_seconds: float = Field(..., ge=0.0, description="Total execution time")
    dry_run: bool = Field(True, description="Whether this was a dry-run")

    # Scanning statistics
    total_books: int = Field(..., ge=0, description="Total books in library")
    books_scanned: int = Field(..., ge=0, description="Books successfully scanned")
    scan_errors: int = Field(0, ge=0, description="Books that failed to scan")

    # Relationship detection
    relationships_found: int = Field(0, ge=0, description="Total relationships detected")
    relationships_by_type: Dict[str, int] = Field(default_factory=dict, description="Breakdown by relationship type")

    # Discrepancy detection
    discrepancies_found: int = Field(0, ge=0, description="Total discrepancies detected")
    discrepancies_by_type: Dict[str, int] = Field(default_factory=dict, description="Breakdown by discrepancy type")
    discrepancies_by_field: Dict[str, int] = Field(default_factory=dict, description="Breakdown by field name")

    # Update statistics
    updates_applied: int = Field(0, ge=0, description="Total metadata updates applied")
    updates_by_field: Dict[str, int] = Field(default_factory=dict, description="Updates per field")
    updates_failed: int = Field(0, ge=0, description="Failed update attempts")

    # Confidence distribution
    confidence_distribution: Dict[str, int] = Field(
        default_factory=lambda: {"<0.5": 0, "0.5-0.7": 0, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 0},
        description="Distribution of confidence scores"
    )

    # Manual review queue
    books_flagged_for_review: int = Field(0, ge=0, description="Books needing manual review")
    review_reasons: Dict[str, int] = Field(default_factory=dict, description="Reasons for manual review")

    # Completeness tracking
    avg_completeness_before: float = Field(0.0, ge=0.0, le=1.0, description="Average completeness before")
    avg_completeness_after: float = Field(0.0, ge=0.0, le=1.0, description="Average completeness after")

    # Validation results
    validation_passed: bool = Field(True, description="Whether post-update validation passed")
    validation_errors: List[str] = Field(default_factory=list, description="Validation error messages")


class HarmonyConfig(BaseModel):
    """Configuration for harmony agent execution"""
    model_config = ConfigDict(extra='forbid')

    # Operational settings
    dry_run: bool = Field(True, description="Analyze only, don't apply updates")
    confidence_threshold: float = Field(0.8, ge=0.0, le=1.0, description="Minimum confidence for auto-apply")
    force_rescan: bool = Field(False, description="Ignore cached data")

    # API settings
    abs_url: str = Field(..., description="Audiobookshelf server URL")
    abs_token: str = Field(..., description="Audiobookshelf API token")
    request_timeout: int = Field(30, ge=1, description="API request timeout in seconds")

    # File paths
    cache_file: str = Field(".harmony_cache.sqlite", description="Cache database path")
    output_dir: str = Field("./reports", description="Report output directory")

    # Logging
    verbose: bool = Field(False, description="Enable verbose logging")
    log_level: str = Field("INFO", description="Logging level")

    @field_validator('abs_url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL is properly formatted"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL: {v}. Must start with http:// or https://")
        return v.rstrip('/')

    @field_validator('abs_token')
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Ensure token is not empty"""
        if not v or not v.strip():
            raise ValueError("Audiobookshelf API token cannot be empty")
        return v.strip()


# Type aliases for convenience
BookGroup = List[BookMetadata]
RelationshipMap = Dict[str, List[Relationship]]
DiscrepancyMap = Dict[str, List[MetadataDiscrepancy]]
