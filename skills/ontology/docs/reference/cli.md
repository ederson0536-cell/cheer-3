# CLI Reference

*Complete command reference for the ontology skill*

---

## Global Options

```bash
python3 scripts/ontology.py [global-options] <command> [command-options]

Global Options:
  --graph PATH       Path to graph file (default: memory/ontology/graph.jsonl)
  --schema PATH      Path to schema file (default: memory/ontology/schema.yaml)
  --format FORMAT    Output format: json, yaml, table (default: table)
  --quiet            Suppress non-error output
  --verbose          Show detailed output
```

---

## Commands

### `create` — Create a new entity

```bash
python3 scripts/ontology.py create \
  --type TYPE \
  --props JSON \
  [--id ID]
```

**Options:**
- `--type` (required) — Entity type (Person, Task, Project, etc.)
- `--props` (required) — JSON object with properties
- `--id` (optional) — Custom ID (auto-generated if omitted)

**Example:**
```bash
python3 scripts/ontology.py create \
  --type Person \
  --props '{"name": "Alice", "email": "alice@example.com"}'
```

**Returns:** The created entity ID

---

### `get` — Retrieve an entity by ID

```bash
python3 scripts/ontology.py get --id ID
```

**Options:**
- `--id` (required) — Entity ID

**Example:**
```bash
python3 scripts/ontology.py get --id person_001
```

**Returns:** Full entity with properties and relations

---

### `list` — List all entities of a type

```bash
python3 scripts/ontology.py list --type TYPE [--limit N]
```

**Options:**
- `--type` (required) — Entity type to list
- `--limit` (optional) — Maximum results (default: 100)

**Example:**
```bash
python3 scripts/ontology.py list --type Task --limit 10
```

**Returns:** Table of entities with key properties

---

### `query` — Search entities by properties

```bash
python3 scripts/ontology.py query \
  --type TYPE \
  --where JSON \
  [--limit N]
```

**Options:**
- `--type` (required) — Entity type to query
- `--where` (required) — JSON filter object
- `--limit` (optional) — Maximum results

**Example:**
```bash
python3 scripts/ontology.py query \
  --type Task \
  --where '{"status": "open", "priority": "high"}'
```

**Returns:** Matching entities

---

### `update` — Modify an entity

```bash
python3 scripts/ontology.py update \
  --id ID \
  --props JSON
```

**Options:**
- `--id` (required) — Entity ID
- `--props` (required) — JSON object with updated properties

**Example:**
```bash
python3 scripts/ontology.py update \
  --id task_001 \
  --props '{"status": "done", "completed_at": "2026-03-10"}'
```

**Returns:** Updated entity

---

### `delete` — Remove an entity

```bash
python3 scripts/ontology.py delete --id ID [--cascade]
```

**Options:**
- `--id` (required) — Entity ID to delete
- `--cascade` (optional) — Also delete related entities

**Example:**
```bash
python3 scripts/ontology.py delete --id task_001
```

**Returns:** Confirmation of deletion

---

### `relate` — Create a relationship

```bash
python3 scripts/ontology.py relate \
  --from ID \
  --rel RELATION_TYPE \
  --to ID \
  [--props JSON]
```

**Options:**
- `--from` (required) — Source entity ID
- `--rel` (required) — Relationship type
- `--to` (required) — Target entity ID
- `--props` (optional) — JSON object with relationship properties

**Example:**
```bash
python3 scripts/ontology.py relate \
  --from proj_001 \
  --rel has_owner \
  --to person_001 \
  --props '{"since": "2026-03-01"}'
```

**Returns:** Confirmation of relationship creation

---

### `unrelate` — Remove a relationship

```bash
python3 scripts/ontology.py unrelate \
  --from ID \
  --rel RELATION_TYPE \
  --to ID
```

**Options:**
- `--from` (required) — Source entity ID
- `--rel` (required) — Relationship type
- `--to` (required) — Target entity ID

**Example:**
```bash
python3 scripts/ontology.py unrelate \
  --from proj_001 \
  --rel has_owner \
  --to person_001
```

**Returns:** Confirmation of relationship removal

---

### `related` — Get related entities

```bash
python3 scripts/ontology.py related \
  --id ID \
  --rel RELATION_TYPE \
  [--direction in|out|both]
```

**Options:**
- `--id` (required) — Entity ID
- `--rel` (required) — Relationship type
- `--direction` (optional) — Direction: in (to entity), out (from entity), both

**Example:**
```bash
python3 scripts/ontology.py related \
  --id proj_001 \
  --rel has_task \
  --direction out
```

**Returns:** List of related entities

---

### `validate` — Check graph integrity

```bash
python3 scripts/ontology.py validate [--fix]
```

**Options:**
- `--fix` (optional) — Attempt to auto-fix issues

**Checks performed:**
- Property constraints (required fields, enums)
- Relation constraints (valid types, cardinality)
- Acyclicity (for relations marked `acyclic: true`)
- Orphaned entities

**Example:**
```bash
python3 scripts/ontology.py validate
```

**Returns:** Validation report

---

### `schema` — Manage type schema

```bash
# View current schema
python3 scripts/ontology.py schema

# Append to schema
python3 scripts/ontology.py schema-append --data JSON

# Validate against schema
python3 scripts/ontology.py schema-validate
```

**Example:**
```bash
python3 scripts/ontology.py schema-append --data '{
  "types": {
    "Meeting": {
      "required": ["title", "start"],
      "properties": {
        "title": "string",
        "start": "datetime",
        "end": "datetime"
      }
    }
  }
}'
```

---

### `tree` — Display entity tree

```bash
python3 scripts/ontology.py tree --id ID [--depth N]
```

**Options:**
- `--id` (required) — Root entity ID
- `--depth` (optional) — Maximum depth (default: 5)

**Example:**
```bash
python3 scripts/ontology.py tree --id proj_001 --depth 3
```

**Returns:** ASCII tree visualization

---

### `export` — Export graph data

```bash
python3 scripts/ontology.py export \
  [--format json|csv|dot] \
  [--output PATH]
```

**Options:**
- `--format` (optional) — Export format
- `--output` (optional) — Output file (stdout if omitted)

**Example:**
```bash
python3 scripts/ontology.py export --format dot --output graph.dot
```

**Returns:** Exported data

---

### `import` — Import graph data

```bash
python3 scripts/ontology.py import --file PATH [--merge]
```

**Options:**
- `--file` (required) — Input file path
- `--merge` (optional) — Merge with existing graph

**Example:**
```bash
python3 scripts/ontology.py import --file backup.jsonl --merge
```

**Returns:** Import report

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Entity not found |
| 4 | Validation failed |
| 5 | Constraint violation |
| 6 | I/O error |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ONTOLOGY_GRAPH` | Default graph file path |
| `ONTOLOGY_SCHEMA` | Default schema file path |
| `ONTOLOGY_FORMAT` | Default output format |

---

## Examples

### Daily Workflow

```bash
# Morning: Check today's tasks
python3 scripts/ontology.py query \
  --type Task \
  --where '{"due": "2026-03-05"}'

# During day: Update task status
python3 scripts/ontology.py update \
  --id task_001 \
  --props '{"status": "in_progress"}'

# End of day: Mark complete
python3 scripts/ontology.py update \
  --id task_001 \
  --props '{"status": "done"}'
```

### Weekly Review

```bash
# Validate graph integrity
python3 scripts/ontology.py validate

# Export for backup
python3 scripts/ontology.py export --output backup-$(date +%Y%m%d).jsonl

# Review project status
python3 scripts/ontology.py tree --id proj_001
```

---

*For more examples, see the [Examples](../examples/) directory.*
