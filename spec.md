# Feature Specification: Audiobookshelf Metadata Harmony Agent

**Feature Branch**: `002-audiobookshelf-metadata-harmony`
**Created**: 2025-10-04
**Status**: Draft
**Input**: User description: "Audiobookshelf Metadata Harmony Agent - Goal: Develop an agent workflow that: 1. Uses the Audiobookshelf API to iterate over every title in the user's library. 2. Scans each title's metadata (author, series, description, publication year, etc.). 3. Compares that data with all other books in the same library to detect potential conjoining metadata (e.g., shared authors or series). 4. Validates matches using confidence-based scoring (e0.8 threshold). 5. For confirmed matches, syncs and updates metadata fields to ensure uniformity across series and author sets. 6. If discrepancies exist, the latest and most complete metadata should overwrite older or incomplete entries. 7. Performs final verification to confirm consistency post-update."

## Clarifications

### Session 2025-10-04
- Q: What happens to metadata below 0.8 confidence threshold - skipped or flagged? → A: Flag for manual review
- Q: How is "latest" metadata determined - by date modified, completeness score, or user selection? → A: Completeness score
- Q: Should the system prompt for confirmation before bulk updates or auto-apply? → A: Auto-apply
- Q: What constitutes "discrepancy" - any difference or semantic differences only? → A: Semantic only

### Session 2025-10-05
- Q: When multiple metadata versions have equal completeness scores, which tie-breaker rule should apply? → A: Prefer metadata with more external identifiers (ISBN/ASIN)
- Q: What is the maximum acceptable library processing time for libraries of different sizes? → A: <1 min per book (linear scaling with size)
- Q: Should the system provide real-time progress updates during harmonization? → A: Yes - live progress bar with current book/total, ETA, completion %
- Q: How should the system handle process interruption (crash, network loss, user cancellation)? → A: User chooses - prompt to resume or restart on next run
- Q: For omnibus editions containing multiple books, how should metadata be handled? → A: Harmonize normally - apply same series metadata as component books
- Q: How should sub-series within universes be handled (e.g., Riftwar Cycle with multiple sub-series)? → A: Hierarchical - preserve both universe and sub-series metadata
- Q: How should author name variations be normalized (e.g., "Liu Cixin" vs "Cixin Liu")? → A: Record all variants, unify links
- Q: How should isolated titles (books with no matching metadata/relationships) be treated? → A: Attempt enrichment - query external sources for missing metadata

---

## Execution Flow (main)
```
1. Parse user description from Input
   � Feature clearly defined: metadata harmonization across library
2. Extract key concepts from description
   � Actors: Library administrator/owner
   � Actions: Scan, compare, validate, sync, verify metadata
   � Data: Book metadata (author, series, description, year)
   � Constraints: Confidence threshold e0.8, non-destructive updates
3. For each unclear aspect:
   � RESOLVED: Low confidence matches flagged for manual review
   � RESOLVED: "Latest" determined by completeness score calculation
   � RESOLVED: Auto-apply mode for high confidence updates
   � RESOLVED: Discrepancies = semantic differences only
4. Fill User Scenarios & Testing section
   � Primary flow: User initiates scan � System harmonizes � User reviews results
5. Generate Functional Requirements
   � All requirements testable and measurable
6. Identify Key Entities
   � Book Metadata, Series, Author, Confidence Score
7. Run Review Checklist
   � WARN "Spec has uncertainties - 4 clarification items marked"
8. Return: SUCCESS (spec ready for clarification phase)
```

---

## � Quick Guidelines
-  Focus on WHAT users need and WHY
- L Avoid HOW to implement (no tech stack, APIs, code structure)
- =e Written for business stakeholders, not developers

---

## User Scenarios & Testing *(mandatory)*

### Primary User Story
As a library owner with multiple audiobooks, I want the system to automatically detect and fix metadata inconsistencies across books in the same series or by the same author, so that my library displays uniform, complete information without manual editing.

### Acceptance Scenarios

1. **Given** a library with 10 books in "Wheel of Time" series where 5 books have series metadata and 5 don't, **When** harmony agent runs, **Then** all 10 books should have identical series metadata with correct sequence numbers.

2. **Given** two books by "Brandon Sanderson" where one lists author as "Brandon Sanderson" and another as "B. Sanderson", **When** harmony agent detects author match above 0.8 confidence, **Then** both books should display the more complete author name "Brandon Sanderson".

3. **Given** books with varying levels of description completeness in the same series, **When** harmony agent identifies the most complete description, **Then** all books in series should receive the complete description while preserving book-specific details.

4. **Given** a dry-run mode execution, **When** harmony agent completes analysis, **Then** system generates preview report of proposed changes without modifying any metadata.

5. **Given** metadata conflict detected with confidence score 0.75, **When** harmony agent processes the library, **Then** book is flagged for manual review rather than auto-updated.

6. **Given** successful metadata harmonization, **When** verification phase runs, **Then** system confirms all related books have consistent metadata and generates completion report.

### Edge Cases
(All critical edge cases have been clarified and incorporated into requirements)

## Requirements *(mandatory)*

### Functional Requirements

**Core Scanning & Analysis**
- **FR-001**: System MUST iterate through every book in the user's library and extract all metadata fields (author, series, series sequence, description, publication year, narrator, ISBN, ASIN, publisher, language, genres, tags)
- **FR-002**: System MUST compare each book's metadata against all other books in the library to identify potential relationships (shared authors, series membership, related works)
- **FR-003**: System MUST calculate confidence scores (0.0-1.0) for each detected metadata relationship using defined scoring criteria
- **FR-004**: System MUST group books by detected relationships (series, author collections, universe groupings)
- **FR-031**: System MUST preserve hierarchical series structure when detected, maintaining both universe-level (e.g., "Riftwar Cycle") and sub-series-level (e.g., "Riftwar Saga") metadata
- **FR-032**: System MUST attempt to enrich metadata for isolated titles (books with no detected relationships) by querying external metadata sources

**Metadata Validation & Scoring**
- **FR-005**: System MUST only process metadata matches with confidence scores e0.8 threshold
- **FR-006**: System MUST flag matches below 0.8 confidence for manual review and include them in a separate review report
- **FR-007**: System MUST determine which metadata is "latest and most complete" by calculating a completeness score (percentage of non-empty fields weighted by field importance), with highest scoring version selected as authoritative; when multiple versions have equal completeness scores, prefer the version with more external identifiers (ISBN/ASIN count)
- **FR-008**: System MUST detect metadata discrepancies defined as semantic differences (meaning-level conflicts), ignoring minor formatting variations, whitespace differences, and equivalent representations (e.g., "2023" vs "2023-01-01")

**Metadata Synchronization**
- **FR-009**: System MUST update incomplete metadata fields with complete versions from related books when confidence e0.8
- **FR-010**: System MUST overwrite outdated or less complete metadata with newer/fuller versions when discrepancies exist
- **FR-011**: System MUST preserve book-specific metadata (individual book descriptions, unique identifiers) while harmonizing series-level metadata
- **FR-012**: System MUST maintain metadata field uniformity across all books in identified series (identical series name, publisher for series, etc.)
- **FR-013**: System MUST never modify or delete audio files, only database metadata records
- **FR-030**: System MUST treat omnibus editions as regular library items and apply series metadata harmonization to them (same author, series information as their component individual books)

**Operational Modes**
- **FR-014**: System MUST support dry-run mode that analyzes and reports proposed changes without applying updates
- **FR-015**: System MUST automatically apply harmonization changes for all matches meeting the confidence threshold, without requiring explicit user confirmation for each update
- **FR-016**: System MUST create backup snapshots of original metadata before any modifications
- **FR-017**: System MUST provide rollback capability to restore previous metadata state
- **FR-028**: System MUST persist progress state during harmonization and detect incomplete runs on startup
- **FR-029**: System MUST prompt user to choose between resuming from last checkpoint or restarting from beginning when previous run was interrupted

**Verification & Reporting**
- **FR-018**: System MUST perform post-update verification confirming metadata consistency across related book groups
- **FR-019**: System MUST generate summary reports containing: total titles analyzed, fields updated count, confidence scores per change, books skipped (below threshold), operation timestamp and duration
- **FR-020**: System MUST maintain full audit logs of all metadata changes including: book ID, field modified, old value, new value, confidence score, timestamp
- **FR-021**: System MUST detect and report verification failures if post-update inconsistencies remain
- **FR-027**: System MUST display live progress updates during harmonization showing: current book being processed, total books processed/remaining, completion percentage, estimated time to completion (ETA)

**Performance Requirements**
- **FR-026**: System MUST complete processing within 1 minute per book (e.g., 100-book library completes within 100 minutes, 1000-book library within ~16.7 hours)

**Authentication & Safety**
- **FR-022**: System MUST authenticate all library operations using provided credentials
- **FR-023**: System MUST validate user has write permissions before attempting metadata updates
- **FR-024**: System MUST handle API rate limiting and implement retry logic for failed requests
- **FR-025**: System MUST gracefully handle partial failures and continue processing remaining books

### Key Entities *(include if feature involves data)*

- **Book Metadata Record**: Represents all metadata for a single audiobook including: title, subtitle, authors (list), series name, series sequence number, description, publication year, narrator, ISBN, ASIN, publisher, language, genres (list), tags (list), last modified date
  - Relationships: Belongs to zero or one Series, authored by one or more Authors

- **Series**: Represents a collection of related books with: series name, sequence numbers, member books
  - Relationships: Contains multiple Books, may belong to a Universe (super-series)

- **Author**: Represents a book author with: primary canonical name, name variations/aliases (list including cultural variations like "Liu Cixin"/"Cixin Liu")
  - Relationships: Authors multiple Books
  - Note: All variant names link to the same author entity for unified relationship tracking

- **Confidence Score**: Numerical value (0.0-1.0) indicating match certainty for: author name matching, series membership detection, metadata similarity assessment
  - Attributes: Score value, scoring criteria used, matched entities

- **Metadata Discrepancy**: Represents detected inconsistency with: affected books, conflicting values, confidence assessment, resolution status
  - Attributes: Discrepancy type (missing, conflicting, incomplete), proposed resolution, requires manual review flag

- **Audit Record**: Historical log entry containing: timestamp, book ID, modified field, old value, new value, data source, confidence score, success/failure status
  - Relationships: References one Book Metadata Record

- **Harmonization Report**: Summary document containing: execution statistics (books scanned, updates applied, errors), confidence distribution, skipped items, timestamp and duration
  - Attributes: Total books, total updates, update breakdown by field, confidence score statistics

---

## Review & Acceptance Checklist

### Content Quality
- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

### Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers remain (all 4 items resolved)
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

---

## Execution Status

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked (4 clarification items)
- [x] Clarifications resolved (all 4 answered)
- [x] User scenarios defined
- [x] Requirements generated (25 functional requirements)
- [x] Entities identified (7 key entities)
- [x] Review checklist passed

---

## Next Steps

✅ All clarifications resolved. The specification is ready for the planning phase.

**Recommended next command**: `/plan` to create the implementation plan from this specification.
