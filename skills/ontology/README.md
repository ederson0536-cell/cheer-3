# Ontology

[![Pattern A](https://img.shields.io/badge/Pattern-A-success)](PATTERN_A.md)

Typed knowledge graph for structured agent memory and composable skills.

## Quick Start

```bash
# Initialize ontology storage
mkdir -p memory/ontology
touch memory/ontology/graph.jsonl

# Create a person
python3 scripts/ontology.py create \
  --type Person \
  --props '{"name":"Alice","email":"alice@example.com"}'

# List all people
python3 scripts/ontology.py list --type Person

# Create a project and link it
python3 scripts/ontology.py create \
  --type Project \
  --props '{"name":"Website Redesign","status":"active"}'

python3 scripts/ontology.py relate \
  --from proj_001 \
  --rel has_owner \
  --to p_001
```

## Structure

```
ontology/
├── SKILL.md              # ClawHub documentation with full spec
└── README.md             # This file
```

## Core Concept

Everything is an **entity** with a **type**, **properties**, and **relations**:

```
Entity: { id, type, properties, relations, created, updated }
Relation: { from_id, relation_type, to_id, properties }
```

## Core Types

### Agents & People
- `Person` — { name, email?, phone?, notes? }
- `Organization` — { name, type?, members[] }

### Work
- `Project` — { name, status, goals[], owner? }
- `Task` — { title, status, due?, priority?, assignee?, blockers[] }
- `Goal` — { description, target_date?, metrics[] }

### Time & Place
- `Event` — { title, start, end?, location?, attendees[], recurrence? }
- `Location` — { name, address?, coordinates? }

### Information
- `Document` — { title, path?, url?, summary? }
- `Message` — { content, sender, recipients[], thread? }
- `Thread` — { subject, participants[], messages[] }
- `Note` — { content, tags[], refs[] }

### Resources
- `Account` — { service, username, credential_ref? }
- `Device` — { name, type, identifiers[] }
- `Credential` — { service, secret_ref }

### Meta
- `Action` — { type, target, timestamp, outcome? }
- `Policy` — { scope, rule, enforcement }

## Storage

Default: `memory/ontology/graph.jsonl`

```jsonl
{"op":"create","entity":{"id":"p_001","type":"Person","properties":{"name":"Alice"}}}
{"op":"create","entity":{"id":"proj_001","type":"Project","properties":{"name":"Website Redesign"}}}
{"op":"relate","from":"proj_001","rel":"has_owner","to":"p_001"}
```

## CLI Usage

### Create Entity
```bash
python3 scripts/ontology.py create \
  --type Person \
  --props '{"name":"Alice","email":"alice@example.com"}'
```

### Query
```bash
python3 scripts/ontology.py query --type Task --where '{"status":"open"}'
python3 scripts/ontology.py get --id task_001
python3 scripts/ontology.py related --id proj_001 --rel has_task
```

### Link Entities
```bash
python3 scripts/ontology.py relate \
  --from proj_001 \
  --rel has_task \
  --to task_001
```

### Validate
```bash
python3 scripts/ontology.py validate
```

## When to Use

| Trigger | Action |
|---------|--------|
| "Remember that..." | Create/update entity |
| "What do I know about X?" | Query graph |
| "Link X to Y" | Create relation |
| "Show all tasks for project Z" | Graph traversal |
| "What depends on X?" | Dependency query |
| Planning multi-step work | Model as graph transformations |
| Skill needs shared state | Read/write ontology objects |

## Schema Definition

Define constraints in `memory/ontology/schema.yaml`:

```yaml
types:
  Task:
    required: [title, status]
    status_enum: [open, in_progress, blocked, done]
  
  Event:
    required: [title, start]
    validate: "end >= start if end exists"

relations:
  has_owner:
    from_types: [Project, Task]
    to_types: [Person]
    cardinality: many_to_one
  
  blocks:
    from_types: [Task]
    to_types: [Task]
    acyclic: true  # No circular dependencies
```

## Append-Only Rule

When working with existing ontology data or schema, **append/merge** changes instead of overwriting files. This preserves history.

## Planning as Graph Transformation

Model multi-step plans as graph operations:

```
Plan: "Schedule team meeting and create follow-up tasks"

1. CREATE Event { title: "Team Sync", attendees: [p_001, p_002] }
2. RELATE Event -> has_project -> proj_001
3. CREATE Task { title: "Prepare agenda", assignee: p_001 }
4. RELATE Task -> for_event -> event_001
```

Each step is validated before execution.

## Related Skills

- `elite-longterm-memory` - Long-term memory integration
- `hierarchical-delegator` - Task delegation with ontology tracking
- `quality-gate-loop` - Quality gates with ontology validation
