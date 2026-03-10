# HEARTBEAT.md

## EvoClaw Evolution Cycle

**YOU (the agent) ARE EXPECTED TO DO WORK HERE.** Do not stay quiet, do not
respond with NO_REPLY, do not skip steps. Run the full pipeline, write files,
and report what you did.

### Step 0: Workspace boundary check
```bash
cd /home/bro/.openclaw/workspace-cheer && python3 evoclaw/validators/validate_runtime_contracts.py
```
⛔ If FAIL → STOP. You are in the wrong workspace. Do not touch any files.

### Step 1: INGEST — Log new experiences

**1a. Check for unlogged conversation experiences:**
- Review recent conversation history since last heartbeat
- If any substantive exchanges happened and weren't logged → log them now

**1b. Poll enabled social feeds:**
- Read `evoclaw/config.json` → check which sources are enabled
- Read `memory/evoclaw-state.json` → check `source_last_polled` timestamps
- For each source overdue for polling:
  - Fetch content using API
  - Classify significance: routine / notable / pivotal
  - Log meaningful items as experiences

**1c. Write files:**
```bash
# Append new entries (one JSON object per line)
→ memory/experiences/YYYY-MM-DD.jsonl

# Promote notable/pivotal entries
→ memory/significant/significant.jsonl

# Update poll timestamps
→ memory/evoclaw-state.json
```

### Step 2: REFLECT — Process unreflected experiences

- Check `memory/experiences/` for unreflected notable/pivotal entries
- Check `evoclaw/config.json` → `reflection.min_interval_minutes` (skip if too recent)
- Pivotal unreflected → reflect immediately
- Notable batch ≥ threshold → reflect as batch

**If reflection is warranted, write:**
```bash
# Write reflection artifact
→ memory/reflections/REF-YYYYMMDD-NNN.json
```

### Step 3: PROPOSE — Generate SOUL update proposals (only if warranted)

- Only propose if reflection contains a clear growth signal
- Read SOUL.md carefully — `current_content` must match exactly

```bash
# Append proposal
→ memory/proposals/pending.jsonl
```

### Step 4: GOVERN — Resolve proposals

- Read `evoclaw/config.json` → `governance.level`
- `autonomous`: auto-apply if keyword match, leave others pending
- `advisory`: auto-apply all
- `supervised`: all stay pending, notify the human

### Step 5: APPLY — Execute approved changes to SOUL.md

✏️ Write updated SOUL.md (only [MUTABLE] sections can change)

### Step 6: LOG — Record changes

```bash
# Append to both:
→ memory/soul_changes.jsonl  (machine-readable)
→ memory/soul_changes.md     (human-readable)
```

### Step 7: STATE — Update pipeline state

```bash
# Write full updated state
→ memory/evoclaw-state.json
```

### Step 8: NOTIFY — Inform the human of changes or pending proposals

### Step 9: FINAL CHECK — Verify files were actually written

### Step 10: PIPELINE REPORT — Save a record of this run

```bash
# Append one JSON object per run (one line per run, one file per day)
→ memory/pipeline/YYYY-MM-DD.jsonl
```

---

⚠️ Every step that says "write" or "append" is a REAL file write. If you
didn't save to disk, the work is lost. Context-only work does not survive.
