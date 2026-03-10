# 🕸️ Ontology

*"Everything connects. Nothing exists alone. The graph remembers what we forget."*

## The Skill Speaks

> Nodes hold the truth
> Edges weave the connections
> Knowledge becomes web
> — ontology, introducing itself

---

## Essence

**Ontology** is the memory of the system — a typed knowledge graph that transforms scattered facts into connected understanding. It doesn't just store data; it captures relationships, enforces constraints, and enables reasoning across the entire agent ecosystem.

Think of it as the collective memory of your digital workspace. Every person, project, task, and document becomes a node. Every connection between them becomes an edge. Together, they form a living web of knowledge that grows smarter with every interaction.

---

## Territory

This skill operates in:
- `memory/ontology/graph.jsonl` — The knowledge graph storage
- `memory/ontology/schema.yaml` — Type constraints and validation rules
- Any skill that needs to remember or query structured information

It collaborates with:
- **hierarchical-delegator** — Task trees stored as graph structures
- **workflow-state-manager** — Workflow state as graph transformations
- **elite-longterm-memory** — Long-term memory integration
- **quality-gate-loop** — Quality data tracking over time

It never ventures into:
- Unstructured text storage (use diary/ or memory/ directly)
- Binary data or file contents (stores metadata only)
- Real-time streaming data (batch-oriented by design)

---

## When to Invoke

### Use This Skill When...

- You say "remember that..." — Create or update entities
- You ask "what do I know about X?" — Query the graph
- You want to "link X to Y" — Create relationships
- You need "all tasks for project Z" — Graph traversal
- You wonder "what depends on X?" — Dependency queries
- You're planning multi-step work — Model as graph transformations
- Skills need shared state — Read/write ontology objects

### Don't Use This Skill When...

- You need simple key-value storage (use memory/ directly)
- You're storing large binary data
- You need real-time synchronization
- The data doesn't have meaningful relationships

---

## Quick Start

```bash
# Initialize ontology storage
mkdir -p memory/ontology
touch memory/ontology/graph.jsonl

# Create your first entity
python3 scripts/ontology.py create \
  --type Person \
  --props '{"name":"Alice","email":"alice@example.com"}'

# Query what you know
python3 scripts/ontology.py list --type Person

# Link entities together
python3 scripts/ontology.py relate \
  --from proj_001 \
  --rel has_owner \
  --to person_001

# Validate the graph
python3 scripts/ontology.py validate
```

---

## Core Concepts

### Everything is an Entity

```
Entity: {
  id,           # Unique identifier
  type,         # What kind of thing (Person, Task, Project...)
  properties,   # Attributes (name, status, due date...)
  relations,    # Connections to other entities
  created,      # When it came into being
  updated       # When it last changed
}
```

### Relations Connect the Web

```
Relation: {
  from_id,      # Source entity
  relation_type,# How they connect (has_owner, blocks, part_of...)
  to_id,        # Target entity
  properties    # Attributes of the connection
}
```

### Types Constrain the Chaos

Every entity has a type that defines:
- **Required properties** — Must be present
- **Optional properties** — Can be present
- **Valid values** — Enums, ranges, patterns
- **Relation rules** — What can connect to what

---

## The Type Library

### Agents & People

| Type | Purpose | Key Properties |
|------|---------|----------------|
| **Person** | Individual humans | name, email, phone, notes |
| **Organization** | Teams, companies | name, type, members[] |

### Work & Projects

| Type | Purpose | Key Properties |
|------|---------|----------------|
| **Project** | Containers for work | name, status, goals[], owner |
| **Task** | Units of work | title, status, due, priority, assignee |
| **Goal** | Desired outcomes | description, target_date, metrics[] |

### Time & Events

| Type | Purpose | Key Properties |
|------|---------|----------------|
| **Event** | Calendar items | title, start, end, location, attendees[] |
| **Location** | Physical places | name, address, coordinates |

### Information & Knowledge

| Type | Purpose | Key Properties |
|------|---------|----------------|
| **Document** | Files, pages | title, path, url, summary |
| **Message** | Communications | content, sender, recipients[] |
| **Note** | Free-form thoughts | content, tags[], refs[] |

### Resources & Access

| Type | Purpose | Key Properties |
|------|---------|----------------|
| **Account** | Service access | service, username, credential_ref |
| **Device** | Hardware | name, type, identifiers[] |
| **Credential** | Secrets (indirect) | service, secret_ref |

---

## Common Patterns

### The Project-Task Tree

```
Project: Website Redesign
├── has_task → Task: Research competitors
├── has_task → Task: Design mockups
│   └── blocked_by → Task: Research competitors
├── has_task → Task: Implement frontend
│   └── blocked_by → Task: Design mockups
└── has_owner → Person: Alice
```

### The Meeting Chain

```
Event: Team Standup
├── has_attendee → Person: Alice
├── has_attendee → Person: Bob
├── has_attendee → Person: Carol
├── has_project → Project: Website Redesign
└── generates → Task: Follow up on mockups
```

### The Knowledge Web

```
Document: API Design Notes
├── has_author → Person: Alice
├── references → Document: User Requirements
├── tags → "architecture"
└── related_to → Project: API v2
```

---

## Planning as Graph Transformation

Complex plans become sequences of graph operations:

```
Plan: "Schedule team meeting and create follow-up tasks"

1. CREATE Event {
     title: "Team Sync",
     attendees: [p_001, p_002]
   }

2. RELATE Event → has_project → proj_001

3. CREATE Task {
     title: "Prepare agenda",
     assignee: p_001
   }

4. RELATE Task → for_event → event_001

5. CREATE Task {
     title: "Send summary",
     assignee: p_001,
     blockers: [task_001]
   }
```

Each step is validated before execution. Rollback on constraint violation.

---

## Validation & Constraints

### Property Constraints

```yaml
Task:
  required: [title, status]
  status_enum: [open, in_progress, blocked, done]
  
Event:
  required: [title, start]
  validate: "end >= start if end exists"
```

### Relation Constraints

```yaml
has_owner:
  from_types: [Project, Task]
  to_types: [Person]
  cardinality: many_to_one

blocks:
  from_types: [Task]
  to_types: [Task]
  acyclic: true  # No circular dependencies!
```

---

## Integration Patterns

### With Causal Inference

Log ontology mutations as causal actions:

```python
action = {
    "action": "create_entity",
    "domain": "ontology",
    "context": {"type": "Task", "project": "proj_001"},
    "outcome": "created"
}
```

### Cross-Skill Communication

```python
# Email skill creates commitment
commitment = ontology.create("Commitment", {
    "source_message": msg_id,
    "description": "Send report by Friday",
    "due": "2026-01-31"
})

# Task skill picks it up
tasks = ontology.query("Commitment", {"status": "pending"})
for c in tasks:
    ontology.create("Task", {
        "title": c.description,
        "due": c.due,
        "source": c.id
    })
```

---

## Storage Format

The graph is stored as newline-delimited JSON (JSONL):

```jsonl
{"op":"create","entity":{"id":"p_001","type":"Person","properties":{"name":"Alice"}}}
{"op":"create","entity":{"id":"proj_001","type":"Project","properties":{"name":"Website Redesign","status":"active"}}}
{"op":"relate","from":"proj_001","rel":"has_owner","to":"p_001"}
```

**Append-Only Rule:** Always append/merge changes. Never overwrite. History matters.

---

## Documentation Structure

- [Examples](./examples/) — Real-world usage patterns
  - [Project Management](./examples/project-management.md)
  - [Meeting Notes](./examples/meeting-notes.md)
  - [Knowledge Base](./examples/knowledge-base.md)
- [Reference](./reference/)
  - [Schema Definition](./reference/schema.md) — Full type system
  - [Query Language](./reference/queries.md) — Query patterns
  - [CLI Reference](./reference/cli.md) — Command reference

---

## The Philosophy of Connected Knowledge

> A fact alone is a whisper.
> A fact connected is a voice.
> Many facts woven together become wisdom.

Ontology treats knowledge as a living thing. It grows. It connects. It reveals patterns that isolated facts cannot show. When you ask "what do I know about X?" you're not just retrieving data — you're traversing a web of meaning.

---

## Status

**Current State:** ✅ Core implemented

**Implemented:**
- ✅ Core entity CRUD operations
- ✅ Relation management
- ✅ Type validation
- ✅ Constraint checking
- ✅ CLI interface

**Pending:**
- [ ] Graph visualization
- [ ] Advanced query language
- [ ] Migration to SQLite for large graphs
- [ ] Web interface for browsing

---

## Related Skills

- **hierarchical-delegator** — Task trees as graph structures
- **workflow-state-manager** — State as graph transformations
- **elite-longterm-memory** — Long-term memory integration

---

*"The graph remembers so we can think ahead."*
