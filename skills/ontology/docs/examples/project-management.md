# Example: Project Management with Ontology

*Tracking a website redesign project through the knowledge graph*

---

## The Scenario

You're managing a website redesign project with multiple team members, tasks, and dependencies. Instead of scattered notes and disconnected tools, you use the ontology to create a connected web of knowledge.

---

## Step 1: Create the People

```bash
# Create team members
python3 scripts/ontology.py create \
  --type Person \
  --props '{
    "name": "Alice Chen",
    "email": "alice@example.com",
    "role": "Project Lead"
  }'
# Returns: person_001

python3 scripts/ontology.py create \
  --type Person \
  --props '{
    "name": "Bob Martinez",
    "email": "bob@example.com",
    "role": "Designer"
  }'
# Returns: person_002

python3 scripts/ontology.py create \
  --type Person \
  --props '{
    "name": "Carol Williams",
    "email": "carol@example.com",
    "role": "Developer"
  }'
# Returns: person_003
```

---

## Step 2: Create the Project

```bash
python3 scripts/ontology.py create \
  --type Project \
  --props '{
    "name": "Website Redesign 2026",
    "status": "active",
    "goals": [
      "Modernize visual design",
      "Improve mobile experience",
      "Increase conversion rates"
    ],
    "start_date": "2026-03-01",
    "target_date": "2026-06-01"
  }'
# Returns: proj_001
```

Link the project to its owner:

```bash
python3 scripts/ontology.py relate \
  --from proj_001 \
  --rel has_owner \
  --to person_001
```

---

## Step 3: Create Tasks

```bash
# Research phase
python3 scripts/ontology.py create \
  --type Task \
  --props '{
    "title": "Research competitor websites",
    "status": "done",
    "priority": "high",
    "due": "2026-03-10"
  }'
# Returns: task_001

# Design phase (depends on research)
python3 scripts/ontology.py create \
  --type Task \
  --props '{
    "title": "Create design mockups",
    "status": "in_progress",
    "priority": "high",
    "due": "2026-03-20"
  }'
# Returns: task_002

# Development phase (depends on design)
python3 scripts/ontology.py create \
  --type Task \
  --props '{
    "title": "Implement frontend components",
    "status": "open",
    "priority": "medium",
    "due": "2026-04-15"
  }'
# Returns: task_003
```

---

## Step 4: Link Everything Together

```bash
# Link tasks to project
python3 scripts/ontology.py relate --from proj_001 --rel has_task --to task_001
python3 scripts/ontology.py relate --from proj_001 --rel has_task --to task_002
python3 scripts/ontology.py relate --from proj_001 --rel has_task --to task_003

# Assign tasks to people
python3 scripts/ontology.py relate --from task_001 --rel assigned_to --to person_001
python3 scripts/ontology.py relate --from task_002 --rel assigned_to --to person_002
python3 scripts/ontology.py relate --from task_003 --rel assigned_to --to person_003

# Create dependencies (design blocked by research)
python3 scripts/ontology.py relate --from task_002 --rel blocked_by --to task_001

# Create dependencies (dev blocked by design)
python3 scripts/ontology.py relate --from task_003 --rel blocked_by --to task_002
```

---

## Step 5: Query the Graph

### Who's working on the project?

```bash
python3 scripts/ontology.py related \
  --id proj_001 \
  --rel has_owner

# Returns: Alice Chen
```

### What tasks are in progress?

```bash
python3 scripts/ontology.py query \
  --type Task \
  --where '{"status": "in_progress"}'

# Returns: Create design mockups (assigned to Bob)
```

### What's blocking Carol's work?

```bash
python3 scripts/ontology.py related \
  --id task_003 \
  --rel blocked_by

# Returns: Create design mockups
```

### What's the full project structure?

```bash
python3 scripts/ontology.py tree --id proj_001

# Returns:
# Website Redesign 2026 (Alice Chen)
# ├── Research competitor websites [done] (Alice)
# ├── Create design mockups [in_progress] (Bob)
# │   └── blocked_by: Research competitor websites
# └── Implement frontend components [open] (Carol)
#     └── blocked_by: Create design mockups
```

---

## The Graph Visualization

```
┌─────────────────────────────────────────────────────────┐
│                    PROJECT                              │
│              Website Redesign 2026                      │
│                      │                                  │
│                      │ has_owner                        │
│                      ▼                                  │
│                ┌──────────┐                             │
│                │  Alice   │                             │
│                │  (Lead)  │                             │
│                └──────────┘                             │
│                      │                                  │
│         ┌────────────┼────────────┐                     │
│         │            │            │                     │
│         ▼            ▼            ▼                     │
│    ┌─────────┐  ┌─────────┐  ┌─────────┐               │
│    │ Research│  │ Design  │  │  Dev    │               │
│    │  [done] │──│[in_prog]│──│  [open] │               │
│    │  Alice  │  │   Bob   │  │  Carol  │               │
│    └─────────┘  └─────────┘  └─────────┘               │
│                      ▲            ▲                     │
│                      │            │                     │
│                      └────────────┘                     │
│                         blocked_by                      │
└─────────────────────────────────────────────────────────┘
```

---

## Why This Matters

Without ontology, this information lives in:
- A project management tool (Asana, Jira)
- Spreadsheets
- Email threads
- People's heads

With ontology, it's all connected:
- Ask "what depends on the research?" → Get design and dev tasks
- Ask "what's Carol blocked on?" → Get Bob's design task
- Ask "what did we learn from competitor research?" → Link to documents

The graph remembers relationships so you don't have to.

---

## Next Steps

- Add documents (research findings, design specs)
- Track meetings and decisions
- Link to external resources
- Add time tracking data

See also:
- [Meeting Notes Example](./meeting-notes.md)
- [Knowledge Base Example](./knowledge-base.md)
