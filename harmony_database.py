#!/usr/bin/env python3
"""
SQLite cache extension for Audiobookshelf Metadata Harmony Agent

Provides:
- relationships table (book_id, related_id, type, confidence, timestamp)
- completeness_scores table (book_id, score, timestamp)
- manual_review_queue table (book_id, reason, flagged_at)
- audit_log table (timestamp, book_id, field, old_value, new_value, confidence, success)
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from harmony_models import (
    Relationship,
    RelationshipType,
    MetadataDiscrepancy,
    AuditRecord,
)


class HarmonyDatabase:
    """
    SQLite database for harmony agent caching and audit logging.

    Tables:
    - relationships: Detected relationships between books
    - completeness_scores: Cached completeness calculations
    - manual_review_queue: Books flagged for manual review
    - audit_log: Full history of all metadata changes
    """

    def __init__(self, db_path: str = ".harmony_cache.sqlite"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._ensure_tables()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_tables(self):
        """Create tables if they don't exist"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Relationships table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    related_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    metadata_used TEXT,  -- JSON array of field names
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(book_id, related_id, relationship_type)
                )
            """)

            # Index for fast lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_relationships_book_id
                ON relationships(book_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_relationships_related_id
                ON relationships(related_id)
            """)

            # Completeness scores table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS completeness_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL UNIQUE,
                    score REAL NOT NULL,
                    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_completeness_book_id
                ON completeness_scores(book_id)
            """)

            # Manual review queue table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS manual_review_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    field_name TEXT,
                    flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved BOOLEAN DEFAULT 0,
                    resolved_at TIMESTAMP,
                    UNIQUE(book_id, field_name, resolved)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_review_queue_book_id
                ON manual_review_queue(book_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_review_queue_resolved
                ON manual_review_queue(resolved)
            """)

            # Audit log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    book_id TEXT NOT NULL,
                    field TEXT NOT NULL,
                    old_value TEXT,  -- JSON serialized
                    new_value TEXT,  -- JSON serialized
                    confidence REAL NOT NULL,
                    data_source TEXT DEFAULT 'harmony_agent',
                    success BOOLEAN DEFAULT 1,
                    error_message TEXT
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_log_book_id
                ON audit_log(book_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp
                ON audit_log(timestamp)
            """)

    # ========== Relationship Methods ==========

    def save_relationship(self, relationship: Relationship) -> int:
        """
        Save or update a relationship.

        Args:
            relationship: Relationship instance to save

        Returns:
            int: Row ID of saved relationship
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            metadata_json = json.dumps(relationship.metadata_used)

            cursor.execute("""
                INSERT OR REPLACE INTO relationships
                (book_id, related_id, relationship_type, confidence, metadata_used, detected_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                relationship.book_id,
                relationship.related_id,
                relationship.relationship_type.value,
                relationship.confidence,
                metadata_json,
                relationship.detected_at.isoformat()
            ))

            return cursor.lastrowid

    def get_relationships(
        self,
        book_id: Optional[str] = None,
        relationship_type: Optional[RelationshipType] = None,
        min_confidence: float = 0.0
    ) -> List[Relationship]:
        """
        Retrieve relationships from cache.

        Args:
            book_id: Filter by book ID (either source or target)
            relationship_type: Filter by relationship type
            min_confidence: Minimum confidence threshold

        Returns:
            List of Relationship instances
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM relationships WHERE confidence >= ?"
            params: List[Any] = [min_confidence]

            if book_id:
                query += " AND (book_id = ? OR related_id = ?)"
                params.extend([book_id, book_id])

            if relationship_type:
                query += " AND relationship_type = ?"
                params.append(relationship_type.value)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            relationships = []
            for row in rows:
                rel = Relationship(
                    book_id=row['book_id'],
                    related_id=row['related_id'],
                    relationship_type=RelationshipType(row['relationship_type']),
                    confidence=row['confidence'],
                    metadata_used=json.loads(row['metadata_used']) if row['metadata_used'] else [],
                    detected_at=datetime.fromisoformat(row['detected_at'])
                )
                relationships.append(rel)

            return relationships

    def clear_relationships(self, book_id: Optional[str] = None):
        """
        Clear relationships from cache.

        Args:
            book_id: If provided, only clear relationships for this book
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if book_id:
                cursor.execute(
                    "DELETE FROM relationships WHERE book_id = ? OR related_id = ?",
                    (book_id, book_id)
                )
            else:
                cursor.execute("DELETE FROM relationships")

    # ========== Completeness Score Methods ==========

    def save_completeness_score(self, book_id: str, score: float):
        """
        Save or update completeness score.

        Args:
            book_id: Book ID
            score: Completeness score (0.0-1.0)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO completeness_scores (book_id, score, calculated_at)
                VALUES (?, ?, ?)
            """, (book_id, score, datetime.now().isoformat()))

    def get_completeness_score(self, book_id: str) -> Optional[float]:
        """
        Retrieve cached completeness score.

        Args:
            book_id: Book ID

        Returns:
            float or None: Cached score, or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT score FROM completeness_scores WHERE book_id = ?",
                (book_id,)
            )
            row = cursor.fetchone()

            return row['score'] if row else None

    def clear_completeness_scores(self):
        """Clear all cached completeness scores"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM completeness_scores")

    # ========== Manual Review Queue Methods ==========

    def add_to_review_queue(
        self,
        book_id: str,
        reason: str,
        field_name: Optional[str] = None
    ):
        """
        Add book to manual review queue.

        Args:
            book_id: Book ID to flag
            reason: Reason for manual review
            field_name: Optional specific field causing issue
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR IGNORE INTO manual_review_queue
                (book_id, reason, field_name, flagged_at)
                VALUES (?, ?, ?, ?)
            """, (book_id, reason, field_name, datetime.now().isoformat()))

    def get_review_queue(self, resolved: bool = False) -> List[Dict[str, Any]]:
        """
        Get items from manual review queue.

        Args:
            resolved: If True, return resolved items; if False, return unresolved

        Returns:
            List of review queue items
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM manual_review_queue WHERE resolved = ? ORDER BY flagged_at",
                (1 if resolved else 0,)
            )
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def mark_review_resolved(self, book_id: str, field_name: Optional[str] = None):
        """
        Mark review queue item as resolved.

        Args:
            book_id: Book ID
            field_name: Optional specific field (if None, resolves all for book)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if field_name:
                cursor.execute("""
                    UPDATE manual_review_queue
                    SET resolved = 1, resolved_at = ?
                    WHERE book_id = ? AND field_name = ? AND resolved = 0
                """, (datetime.now().isoformat(), book_id, field_name))
            else:
                cursor.execute("""
                    UPDATE manual_review_queue
                    SET resolved = 1, resolved_at = ?
                    WHERE book_id = ? AND resolved = 0
                """, (datetime.now().isoformat(), book_id))

    # ========== Audit Log Methods ==========

    def log_audit_record(self, record: AuditRecord) -> int:
        """
        Save audit log entry.

        Args:
            record: AuditRecord instance

        Returns:
            int: Row ID of log entry
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO audit_log
                (timestamp, book_id, field, old_value, new_value, confidence,
                 data_source, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.timestamp.isoformat(),
                record.book_id,
                record.field,
                json.dumps(record.old_value),
                json.dumps(record.new_value),
                record.confidence,
                record.data_source,
                record.success,
                record.error_message
            ))

            return cursor.lastrowid

    def get_audit_log(
        self,
        book_id: Optional[str] = None,
        field: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditRecord]:
        """
        Retrieve audit log entries.

        Args:
            book_id: Filter by book ID
            field: Filter by field name
            limit: Maximum number of entries to return

        Returns:
            List of AuditRecord instances
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM audit_log WHERE 1=1"
            params: List[Any] = []

            if book_id:
                query += " AND book_id = ?"
                params.append(book_id)

            if field:
                query += " AND field = ?"
                params.append(field)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            records = []
            for row in rows:
                record = AuditRecord(
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    book_id=row['book_id'],
                    field=row['field'],
                    old_value=json.loads(row['old_value']) if row['old_value'] else None,
                    new_value=json.loads(row['new_value']) if row['new_value'] else None,
                    confidence=row['confidence'],
                    data_source=row['data_source'],
                    success=bool(row['success']),
                    error_message=row['error_message']
                )
                records.append(record)

            return records

    # ========== Statistics Methods ==========

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with counts and summary info
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Relationship counts
            cursor.execute("SELECT COUNT(*) as count FROM relationships")
            stats['total_relationships'] = cursor.fetchone()['count']

            cursor.execute("""
                SELECT relationship_type, COUNT(*) as count
                FROM relationships
                GROUP BY relationship_type
            """)
            stats['relationships_by_type'] = {
                row['relationship_type']: row['count']
                for row in cursor.fetchall()
            }

            # Completeness scores
            cursor.execute("SELECT COUNT(*) as count FROM completeness_scores")
            stats['cached_scores'] = cursor.fetchone()['count']

            cursor.execute("SELECT AVG(score) as avg FROM completeness_scores")
            avg_row = cursor.fetchone()
            stats['avg_completeness'] = avg_row['avg'] if avg_row['avg'] else 0.0

            # Review queue
            cursor.execute("SELECT COUNT(*) as count FROM manual_review_queue WHERE resolved = 0")
            stats['pending_reviews'] = cursor.fetchone()['count']

            # Audit log
            cursor.execute("SELECT COUNT(*) as count FROM audit_log")
            stats['total_audit_entries'] = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM audit_log WHERE success = 1")
            stats['successful_updates'] = cursor.fetchone()['count']

            return stats

    def vacuum(self):
        """Optimize database (reclaim space, rebuild indexes)"""
        with self._get_connection() as conn:
            conn.execute("VACUUM")


# Export
__all__ = ['HarmonyDatabase']
