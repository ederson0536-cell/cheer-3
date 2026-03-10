# Memory System Single-Write-Source Convergence Plan (Cheer)

## Target

- **Single source of truth:** `memory/memory.db`.
- Execution-state and evolution-state master data must be written to DB first.
- `json` / `jsonl` files are only:
  1. **Projection outputs** (report/debug/compat), or
  2. **Archive snapshots** (immutable audit/export).

## Current Contract Artifacts

- Ownership contract (machine-readable):
  - `evoclaw/runtime/contracts/memory_db_ownership.json`
- Contract validator:
  - `evoclaw/validators/check_memory_db_ownership.py`
- Integrated into orchestrator:
  - `evoclaw/validators/run_all.py`

## Ownership Definition (DB-first)

The ownership contract defines, for each canonical table:

- table owner (single writer responsibility)
- purpose
- field-level source origin (`field_sources`)

Canonical tables covered:

- `memories`
- `proposals`
- `reflections`
- `graph_entities`
- `graph_relations`
- `soul_history`
- `rules`
- `candidates`
- `system_state`
- `system_logs`

## Write Policy

### 1) Primary writes (required)

All business-critical writes must go to `memory.db` using `SQLiteMemoryStore` APIs.

### 2) Projection writes (optional)

Projection files must be explicitly tagged as derived artifacts.
Recommended path patterns:

- `memory/projections/**`
- `memory/reports/**`
- `logs/**`

### 3) Archive snapshots (optional)

Archive-only snapshots should be immutable and timestamped.
Recommended path patterns:

- `memory/archive/**`

## Migration Guidance (JSON/JSONL -> DB)

For legacy writers still targeting `memory/*.jsonl` directly:

1. Keep existing file output temporarily as compatibility projection.
2. Add DB write path first (canonical write).
3. Mark file output as derived in code comments and docs.
4. Add parity checks for key records during transition.
5. Remove direct file writes once all readers use DB queries.

## Acceptance Gates

- `test_sqlite_memory` must remain green.
- `check_memory_db_ownership.py` must pass.
- Future PRs that add/rename DB tables must update ownership contract in same change.

## Non-Goals (this phase)

- This phase does **not** remove all existing JSON/JSONL readers/writers.
- It establishes ownership and enforcement scaffolding so the codebase can converge incrementally without data loss.
