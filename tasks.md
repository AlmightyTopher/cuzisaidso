# Implementation Tasks: Audiobookshelf Metadata Harmony Agent

**Feature Branch**: `002-audiobookshelf-metadata-harmony`
**Created**: 2025-10-04
**Base Directory**: `C:\Users\dogma\Projects\allgendownload`

---

## Task Execution Guide

### Parallel Execution

Tasks marked with **[P]** can be executed in parallel. Example:

```bash
# Run 3 parallel test tasks
Task("Write unit tests for completeness calculator") & \
Task("Write unit tests for relationship detector") & \
Task("Write unit tests for semantic diff engine")
```

### Dependencies

- **Sequential**: Tasks without [P] must complete before next task
- **Parallel**: Tasks with [P] in same phase can run concurrently
- **Cross-Phase**: All tasks in Phase N must complete before Phase N+1

---

## Phase 0: Project Setup & Environment

### T001: Initialize Project Structure
**File**: `src/harmony_agent/__init__.py`
**Description**: Create the harmony_agent package structure
**Actions**:
- Create directory: `src/harmony_agent/`
- Create `__init__.py` with package metadata
- Create subdirectories: `agents/`, `utils/`, `tests/`
- Add to version control

**Dependencies**: None

---

### T002: Install Dependencies [P]
**File**: `requirements.txt`
**Description**: Set up Python dependencies for harmony agent
**Actions**:
- Create `requirements-harmony.txt` with:
  ```
  httpx>=0.27,<1.0
  pydantic>=2.11,<3.0
  python-dotenv>=1.1,<2.0
  rapidfuzz>=3.14,<4.0
  tenacity>=9.1,<10.0
  pytest>=8.4,<9.0
  pytest-asyncio>=1.2,<2.0
  respx>=0.22,<1.0
  ```
- Run: `pip install -r requirements-harmony.txt`
- Verify all imports work

**Dependencies**: T001

---

### T003: Configure Environment [P]
**File**: `.env.harmony.example`
**Description**: Create configuration template
**Actions**:
- Create `.env.harmony.example` with template variables
- Document all configuration options
- Create `.env.harmony` from template (gitignored)
- Test loading with python-dotenv

**Dependencies**: T001

---

### T004: Setup Logging Configuration [P]
**File**: `src/harmony_agent/utils/logging_config.py`
**Description**: Configure structured logging
**Actions**:
- Create logging config module
- Set up file and console handlers
- Configure log levels (INFO, DEBUG, ERROR)
- Add rotation for log files
- Test logging output

**Dependencies**: T001

---

## Phase 1: Data Models & Core Utilities

### T005: Define Extended Book Metadata Model [P]
**File**: `src/harmony_agent/models.py`
**Description**: Create Pydantic models for harmony-specific metadata
**Actions**:
- Extend `BookMetadata` from abs_updater with:
  - `completeness_score: float`
  - `related_book_ids: List[str]`
  - `needs_manual_review: bool`
  - `last_harmony_check: Optional[datetime]`
- Define `Relationship` model
- Define `MetadataDiscrepancy` model
- Define `CompletionReport` model
- Add validation rules and examples

**Dependencies**: T002

---

### T006: Write Unit Tests for Book Models [P]
**File**: `tests/harmony_agent/test_models.py`
**Description**: Test data model validation
**Actions**:
- Test `BookMetadata` validation (required fields)
- Test `Relationship` confidence constraints (0.0-1.0)
- Test `MetadataDiscrepancy` structure
- Test `CompletionReport` aggregation
- Test model serialization/deserialization

**Dependencies**: T005

---

### T007: Implement Completeness Calculator [P]
**File**: `src/harmony_agent/utils/completeness.py`
**Description**: Calculate weighted completeness scores
**Actions**:
- Define field weights (description=0.9, publisher=0.6, etc.)
- Implement `calculate_completeness_score(book)` function
- Handle list fields (genres, tags, authors)
- Handle optional fields (narrator, isbn, asin)
- Return 0.0-1.0 score

**Dependencies**: T005

---

### T008: Write Unit Tests for Completeness Calculator [P]
**File**: `tests/harmony_agent/test_completeness.py`
**Description**: Test completeness scoring logic
**Actions**:
- Test empty book returns 0.0
- Test fully complete book returns 1.0
- Test weighted scoring (description > tags)
- Test list field handling (non-empty counts)
- Test edge cases (None vs empty string)

**Dependencies**: T007

---

### T009: Implement Semantic Diff Engine [P]
**File**: `src/harmony_agent/utils/semantic_diff.py`
**Description**: Detect semantic equivalence between values
**Actions**:
- Implement `is_semantically_equivalent(val1, val2, field_type)`
- Handle year extraction ("2023" == "2023-01-01")
- Handle name normalization (whitespace, case, punctuation)
- Use rapidfuzz for fuzzy matching (≥90% = same)
- Return boolean equivalence

**Dependencies**: T002

---

### T010: Write Unit Tests for Semantic Diff [P]
**File**: `tests/harmony_agent/test_semantic_diff.py`
**Description**: Test semantic equivalence detection
**Actions**:
- Test date format variations ("2023" == "2023-01-01")
- Test whitespace ignored (" Title " == "Title")
- Test case insensitivity ("title" == "Title")
- Test punctuation ignored ("Title!" == "Title")
- Test fuzzy author matching ("B. Sanderson" ≈ "Brandon Sanderson")

**Dependencies**: T009

---

### T011: Extend Cache Layer for Harmony Data
**File**: `src/harmony_agent/utils/cache.py`
**Description**: Add harmony-specific cache tables
**Actions**:
- Extend existing SQLite cache from abs_updater
- Add table: `relationships` (book_id, related_id, type, confidence)
- Add table: `completeness_scores` (book_id, score, timestamp)
- Add table: `manual_review_queue` (book_id, reason, flagged_at)
- Add indexes for performance
- Write migration script

**Dependencies**: T005

---

### T012: Write Unit Tests for Cache Extension [P]
**File**: `tests/harmony_agent/test_cache.py`
**Description**: Test new cache tables
**Actions**:
- Test relationship insertion and retrieval
- Test completeness score caching
- Test manual review queue operations
- Test cache invalidation logic
- Test concurrent access safety

**Dependencies**: T011

---

## Phase 2: Agent Implementation

### T013: Implement Relationship Detector Agent
**File**: `src/harmony_agent/agents/detector.py`
**Description**: Detect relationships between books
**Actions**:
- Create `RelationshipDetector` class
- Implement `detect_author_matches()` using fuzzy matching
- Implement `detect_series_membership()` using series name + sequence
- Implement `detect_universe_groupings()` for super-series
- Calculate confidence scores for each relationship
- Return list of `Relationship` objects

**Dependencies**: T005, T009

---

### T014: Write Unit Tests for Relationship Detector [P]
**File**: `tests/harmony_agent/test_detector.py`
**Description**: Test relationship detection logic
**Actions**:
- Test author fuzzy match ("B. Sanderson" → "Brandon Sanderson")
- Test series detection (same series name + sequence)
- Test universe grouping (Riftwar sub-series)
- Test confidence threshold filtering (<0.8 excluded)
- Test no relationships for isolated books

**Dependencies**: T013

---

### T015: Implement Metadata Comparator Agent
**File**: `src/harmony_agent/agents/comparator.py`
**Description**: Compare metadata across related books
**Actions**:
- Create `MetadataComparator` class
- Implement `find_discrepancies(book_group, fields)`
- Use semantic diff to detect conflicts
- Prioritize discrepancies by impact (title > tags)
- Return list of `MetadataDiscrepancy` objects

**Dependencies**: T005, T009

---

### T016: Write Unit Tests for Metadata Comparator [P]
**File**: `tests/harmony_agent/test_comparator.py`
**Description**: Test discrepancy detection
**Actions**:
- Test semantic equivalence bypass (no false positives)
- Test true discrepancy detection (different meanings)
- Test field prioritization (critical vs minor fields)
- Test handling of missing values (None vs empty)
- Test edge case: all books have different values

**Dependencies**: T015

---

### T017: Extend Metadata Merger for Completeness
**File**: `src/harmony_agent/utils/metadata_merger.py`
**Description**: Extend abs_updater merger with completeness logic
**Actions**:
- Import existing `MetadataMerger` from abs_updater
- Override `select_authoritative_value()` method
- Add `merge_by_completeness()` method
- Integrate completeness scorer
- Preserve book-specific metadata (individual descriptions)

**Dependencies**: T007, T013

---

### T018: Write Unit Tests for Metadata Merger [P]
**File**: `tests/harmony_agent/test_merger.py`
**Description**: Test completeness-based merging
**Actions**:
- Test select by completeness (picks highest score)
- Test preserve book-specific metadata
- Test harmonize series-level metadata (uniform series name)
- Test dry-run mode (reports only, no changes)
- Test confidence threshold enforcement

**Dependencies**: T017

---

### T019: Implement Validation Agent
**File**: `src/harmony_agent/agents/validator.py`
**Description**: Verify post-update consistency
**Actions**:
- Create `ValidationAgent` class
- Implement `verify_series_consistency(series_name, books)`
- Implement `verify_author_consistency(author_name, books)`
- Check metadata uniformity across groups
- Return bool success + detailed error messages

**Dependencies**: T005

---

### T020: Write Unit Tests for Validation Agent [P]
**File**: `tests/harmony_agent/test_validator.py`
**Description**: Test validation logic
**Actions**:
- Test series consistency pass (all books match)
- Test series consistency fail (discrepancy remains)
- Test author consistency verification
- Test validation of completeness scores
- Test handling of empty groups

**Dependencies**: T019

---

### T021: Extend Scanner Agent for Completeness Scoring
**File**: `src/harmony_agent/agents/scanner.py`
**Description**: Add completeness calculation to scanner
**Actions**:
- Import `ScannerAgent` from abs_updater
- Add method: `calculate_completeness_score(book)`
- Integrate completeness calculator utility
- Cache scores in extended cache layer
- Return books with completeness scores populated

**Dependencies**: T007, T011

---

### T022: Write Unit Tests for Extended Scanner [P]
**File**: `tests/harmony_agent/test_scanner.py`
**Description**: Test scanner completeness integration
**Actions**:
- Test completeness score calculation during scan
- Test caching of scores
- Test score invalidation on metadata change
- Test batch processing of large libraries
- Test error handling for malformed books

**Dependencies**: T021

---

## Phase 3: Orchestration & Workflow

### T023: Implement Harmony Orchestrator
**File**: `src/harmony_agent/orchestrator.py`
**Description**: Coordinate all agents in workflow
**Actions**:
- Create `HarmonyOrchestrator` class
- Implement 5-phase workflow:
  1. Scan & Score
  2. Detect Relationships
  3. Compare & Find Discrepancies
  4. Merge & Apply (if not dry-run)
  5. Validate
- Add error handling and rollback logic
- Generate `CompletionReport`
- Support dry-run and live update modes

**Dependencies**: T013, T015, T017, T019, T021

---

### T024: Write Integration Tests for Orchestrator [P]
**File**: `tests/harmony_agent/test_integration.py`
**Description**: End-to-end workflow testing
**Actions**:
- Test full pipeline success (dry-run mode)
- Test pipeline with actual updates applied
- Test confidence threshold filtering (low confidence skipped)
- Test rollback on error (backup restored)
- Test manual review queue population

**Dependencies**: T023

---

## Phase 4: CLI & User Interface

### T025: Implement CLI Interface
**File**: `harmony_agent.py`
**Description**: Create command-line interface
**Actions**:
- Use `argparse` for CLI parsing
- Add arguments:
  - `--dry-run` (default: True)
  - `--update` (disables dry-run)
  - `--confidence` (default: 0.8)
  - `--verbose` (enable debug logging)
- Call orchestrator with parsed config
- Display progress and results
- Handle keyboard interrupts gracefully

**Dependencies**: T023

---

### T026: Write CLI Tests [P]
**File**: `tests/harmony_agent/test_cli.py`
**Description**: Test command-line interface
**Actions**:
- Test argument parsing (all flags)
- Test dry-run vs update mode
- Test confidence threshold validation
- Test verbose logging output
- Test exit codes (success vs error)

**Dependencies**: T025

---

## Phase 5: Reporting & Audit

### T027: Implement Report Generator
**File**: `src/harmony_agent/utils/reporting.py`
**Description**: Generate completion reports
**Actions**:
- Create JSON summary report (statistics)
- Create CSV operations report (all updates)
- Create CSV review report (flagged items)
- Include timestamps, confidence scores, file paths
- Format for human readability

**Dependencies**: T023

---

### T028: Write Report Tests [P]
**File**: `tests/harmony_agent/test_reporting.py`
**Description**: Test report generation
**Actions**:
- Test JSON summary format
- Test CSV operations format
- Test CSV review queue format
- Test report file creation
- Test report data accuracy

**Dependencies**: T027

---

### T029: Implement Audit Logging
**File**: `src/harmony_agent/utils/audit.py`
**Description**: Log all operations for audit trail
**Actions**:
- Log relationship detections
- Log discrepancies found
- Log updates applied (before/after values)
- Log manual review items
- Use structured logging (JSON format)
- Rotate log files daily

**Dependencies**: T004

---

### T030: Write Audit Logging Tests [P]
**File**: `tests/harmony_agent/test_audit.py`
**Description**: Test audit logging
**Actions**:
- Test log entry creation
- Test log file rotation
- Test structured JSON format
- Test log filtering by level
- Test audit trail completeness

**Dependencies**: T029

---

## Phase 6: Backup & Rollback

### T031: Implement Backup System
**File**: `src/harmony_agent/agents/backup.py`
**Description**: Create pre-update snapshots
**Actions**:
- Reuse `BackupAgent` from abs_updater
- Create backup before each update
- Store in `./backups/harmony_<timestamp>/`
- Save as JSON for easy inspection
- Include metadata and timestamp

**Dependencies**: T023

---

### T032: Implement Rollback Mechanism [P]
**File**: `src/harmony_agent/utils/rollback.py`
**Description**: Restore from backups
**Actions**:
- Load backup by timestamp
- Restore metadata to ABS via API
- Verify restoration success
- Log rollback operations
- Support partial rollback (specific books)

**Dependencies**: T031

---

### T033: Write Backup/Rollback Tests [P]
**File**: `tests/harmony_agent/test_backup.py`
**Description**: Test backup and rollback
**Actions**:
- Test backup creation before updates
- Test backup file structure
- Test rollback restoration
- Test rollback verification
- Test partial rollback scenarios

**Dependencies**: T031, T032

---

## Phase 7: Performance & Optimization

### T034: Implement Parallel Processing [P]
**File**: `src/harmony_agent/utils/parallel.py`
**Description**: Optimize with concurrent execution
**Actions**:
- Add worker pool for relationship detection
- Use asyncio for concurrent API calls
- Implement semaphore for rate limiting
- Batch cache operations
- Profile performance

**Dependencies**: T023

---

### T035: Write Performance Tests [P]
**File**: `tests/harmony_agent/test_performance.py`
**Description**: Benchmark performance targets
**Actions**:
- Test scanning speed (<5s for 1,300 books)
- Test relationship detection (<30s)
- Test harmonization (<20s)
- Test total runtime (<2 minutes)
- Test memory usage (<1GB)

**Dependencies**: T034

---

### T036: Optimize Cache Strategy [P]
**File**: `src/harmony_agent/utils/cache_optimizer.py`
**Description**: Improve cache hit rates
**Actions**:
- Add cache preloading
- Implement cache warming on startup
- Add cache statistics tracking
- Optimize SQLite indexes
- Implement cache eviction policy

**Dependencies**: T011

---

## Phase 8: Documentation & Polish

### T037: Write README Documentation [P]
**File**: `README_HARMONY_AGENT.md`
**Description**: Create user documentation
**Actions**:
- Overview & purpose
- Installation instructions
- Quick start guide
- Configuration options
- CLI usage examples
- Troubleshooting section

**Dependencies**: T025

---

### T038: Generate API Documentation [P]
**File**: `docs/api.md`
**Description**: Document code interfaces
**Actions**:
- Agent class interfaces
- Utility function signatures
- Data model schemas
- Extension points
- Usage examples

**Dependencies**: T023

---

### T039: Write Integration Scenarios [P]
**File**: `docs/scenarios.md`
**Description**: Document real-world use cases
**Actions**:
- Scenario: Harmonize series metadata
- Scenario: Fix author name inconsistencies
- Scenario: Handle omnibus editions
- Scenario: Manual review workflow
- Include expected outcomes

**Dependencies**: T024

---

### T040: Final Testing & Validation
**File**: `tests/harmony_agent/test_acceptance.py`
**Description**: Acceptance testing against spec requirements
**Actions**:
- Test all 25 functional requirements (FR-001 to FR-025)
- Test all 6 acceptance scenarios from spec
- Test all edge cases listed in spec
- Verify dry-run mode safety
- Verify confidence threshold enforcement
- Achieve ≥85% test coverage

**Dependencies**: All previous tasks

---

## Execution Summary

**Total Tasks**: 40
**Parallelizable**: 24 tasks (60%)
**Estimated Timeline**:
- Phase 0-2: 3 days (setup + core)
- Phase 3-4: 2 days (orchestration + CLI)
- Phase 5-6: 1 day (reporting + backup)
- Phase 7-8: 1 day (optimization + docs)
- **Total**: ~7 days

**Success Criteria**:
- ✅ All 40 tasks completed
- ✅ Test coverage ≥85%
- ✅ All 25 functional requirements met
- ✅ Performance benchmarks achieved
- ✅ Documentation complete
- ✅ Zero data loss in testing

**Next Action**: Begin with T001-T004 (setup tasks) in parallel.
