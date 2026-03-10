#!/usr/bin/env python3
"""
EvoClaw Feedback System
Based on SYSTEM_FRAMEWORK_PROPOSAL.md - Four Hooks + Governance
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from hashlib import sha1
from typing import Any
from uuid import uuid4

WORKSPACE = Path(__file__).resolve().parents[1]
MEMORY = WORKSPACE / "memory"
CONFIRMATION_STATE_KEY = "feedback_confirmation_pending"
SATISFACTION_PROMPT = "这个回答满足你的需求吗？"

from evoclaw.sqlite_memory import SQLiteMemoryStore
from evoclaw.runtime.hooks.before_task import run_before_task as run_runtime_before_task
from evoclaw.runtime.observability import increment_metric

_MEMORY_STORE = None

def _get_memory_store():
    global _MEMORY_STORE
    if _MEMORY_STORE is None:
        store = SQLiteMemoryStore(MEMORY / "memory.db")
        store.init_schema()
        _MEMORY_STORE = store
    return _MEMORY_STORE

DB_WRITE_RETRY_QUEUE = MEMORY / "retry" / "db_write_failures.jsonl"
DB_WRITE_ERROR_COUNTER_KEY = "db_write_error_counter"


def _enqueue_db_retry(label: str, payload: Any, error: Exception) -> None:
    DB_WRITE_RETRY_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": f"db-retry-{uuid4().hex}",
        "timestamp": datetime.now().isoformat(),
        "label": label,
        "error": str(error),
        "payload": payload,
    }
    with open(DB_WRITE_RETRY_QUEUE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _record_db_write_failure(label: str, payload: Any, error: Exception) -> None:
    now = datetime.now().isoformat()
    db_path = MEMORY / "memory.db"
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO system_logs (
                    id, log_type, source, content, created_at, updated_at,
                    level, metadata_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"db-write-fail-{uuid4().hex[:16]}",
                    "db_write_failure",
                    "feedback_system",
                    f"DB write failed for {label}: {error}",
                    now,
                    now,
                    "error",
                    json.dumps({"label": label, "error": str(error)}, ensure_ascii=False),
                    json.dumps({"payload": payload}, ensure_ascii=False),
                ),
            )

            row = conn.execute(
                "SELECT value_json FROM system_state WHERE key = ?",
                (DB_WRITE_ERROR_COUNTER_KEY,),
            ).fetchone()
            count = 0
            if row and row[0]:
                try:
                    count = int(json.loads(row[0]).get("count", 0))
                except Exception:
                    count = 0
            count += 1
            conn.execute(
                "INSERT OR REPLACE INTO system_state (key, value_json, updated_at) VALUES (?, ?, ?)",
                (
                    DB_WRITE_ERROR_COUNTER_KEY,
                    json.dumps({"count": count, "last_label": label, "last_error": str(error)}, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
    except Exception as log_err:
        print(f"~ Failed to record db_write_failure log: {log_err}")


def _safe_db_write(action, payload, label):
    try:
        action(payload)
        increment_metric("db_write_success_total", source="feedback_system", metadata={"label": label})
    except Exception as e:
        print(f"~ DB sync failed for {label}: {e}")
        increment_metric("db_write_failed_total", source="feedback_system", metadata={"label": label, "error": str(e)[:200]})
        _enqueue_db_retry(label, payload, e)
        _record_db_write_failure(label, payload, e)

def init_feedback_system():
    """Initialize feedback storage."""
    _get_memory_store().init_schema()
    print("✓ Feedback system initialized")


def _extract_terms(task: dict) -> list[str]:
    tokens: list[str] = []
    for key in ("name", "type", "sender", "message"):
        value = task.get(key)
        if not value:
            continue
        for piece in str(value).strip().split():
            piece = piece.strip().lower()
            if len(piece) >= 2:
                tokens.append(piece)
    return list(dict.fromkeys(tokens))[:8]


def _load_before_task_references(task: dict) -> dict:
    """Load rules/candidates/memories/graph references from SQLite."""
    db_path = MEMORY / "memory.db"
    if not db_path.exists():
        return {"rules": [], "candidates": [], "memories": [], "graph": []}

    terms = _extract_terms(task)
    results = {"rules": [], "candidates": [], "memories": [], "graph": []}

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row

            # 1) rules: priority / scope / action
            rule_rows = conn.execute(
                """
                SELECT id, priority, scope, action, content, source_proposal_id, created_at
                FROM rules
                WHERE enabled = 1
                ORDER BY created_at DESC, id DESC
                LIMIT 30
                """
            ).fetchall()
            for row in rule_rows:
                item = dict(row)
                raw_content = item.get("content")
                try:
                    item["content_json"] = json.loads(raw_content) if raw_content else {}
                except Exception:
                    item["content_json"] = {}
                results["rules"].append(item)

            # 2) candidates: skill_id / task_type / score
            task_type = str(task.get("type") or "")
            cand_rows = conn.execute(
                """
                SELECT id, skill_id, task_type, score, status, source, updated_at
                FROM candidates
                WHERE (? = '' OR task_type = ?)
                ORDER BY score DESC, updated_at DESC
                LIMIT 20
                """,
                (task_type, task_type),
            ).fetchall()
            results["candidates"] = [dict(r) for r in cand_rows]

            # 3) memories: FTS keyword search
            if terms:
                match_expr = " OR ".join(terms)
                mem_rows = conn.execute(
                    """
                    SELECT
                        m.id, m.type, m.content, m.source, m.created_at, m.significance,
                        bm25(memories_fts) AS score
                    FROM memories_fts
                    JOIN memories m ON m.rowid = memories_fts.rowid
                    WHERE memories_fts MATCH ?
                    ORDER BY score
                    LIMIT 20
                    """,
                    (match_expr,),
                ).fetchall()
                results["memories"] = [dict(r) for r in mem_rows]

            # 4) graph: entity + relation context
            if terms:
                like_parts = []
                params = []
                for t in terms:
                    p = f"%{t}%"
                    like_parts.append(
                        "(LOWER(ge.entity_type) LIKE ? OR LOWER(COALESCE(ge.name,'')) LIKE ? OR LOWER(ge.properties_json) LIKE ?)"
                    )
                    params.extend([p, p, p])
                where_sql = " OR ".join(like_parts)
                graph_rows = conn.execute(
                    f"""
                    SELECT
                        ge.id AS entity_id,
                        ge.entity_type,
                        COALESCE(ge.name, '') AS name,
                        ge.properties_json,
                        gr.id AS relation_id,
                        gr.source_id,
                        gr.target_id,
                        gr.relation_type
                    FROM graph_entities ge
                    LEFT JOIN graph_relations gr
                      ON gr.source_id = ge.id OR gr.target_id = ge.id
                    WHERE {where_sql}
                    ORDER BY ge.created_at DESC
                    LIMIT 20
                    """,
                    params,
                ).fetchall()
                results["graph"] = [dict(r) for r in graph_rows]
    except Exception as e:
        print(f"~ Reference query skipped: {e}")

    return results

# ========== Four Hooks ==========

def before_task(task):
    """Hook: Before task starts"""
    runtime_result = None
    references = {"rules": [], "candidates": [], "memories": [], "graph": []}

    message = str(task.get("message") or task.get("name") or "").strip()
    if message:
        try:
            runtime_result = run_runtime_before_task(message=message, context=task)
            retrieval = runtime_result.get("memory_retrieval", {})
            rules_track = retrieval.get("rules_track", {})
            experience_track = retrieval.get("experience_track", {})
            graph_track = retrieval.get("graph_track", {})
            candidates_track = retrieval.get("candidates_track", {})

            rules = rules_track.get("rules", {}) if isinstance(rules_track, dict) else {}
            flat_rules = []
            for bucket in ("P0_HARD", "P1_GOVERNANCE", "P2_TASK_TYPE", "P3_SCENARIO", "P4_SUGGESTION"):
                items = rules.get(bucket, [])
                if isinstance(items, list):
                    flat_rules.extend(items)

            references = {
                "rules": flat_rules,
                "candidates": candidates_track.get("candidates", []) if isinstance(candidates_track, dict) else [],
                "memories": experience_track.get("episodic", {}).get("similar_tasks", []) if isinstance(experience_track, dict) else [],
                "graph": graph_track.get("matches", []) if isinstance(graph_track, dict) else [],
            }
        except Exception as e:
            print(f"~ runtime before_task skipped: {e}")
            references = _load_before_task_references(task)
    else:
        references = _load_before_task_references(task)

    feedback = {
        "hook": "before_task",
        "task": task,
        "references": references,
        "runtime_before_task": _runtime_before_task_summary(runtime_result),
        "timestamp": datetime.now().isoformat(),
        "status": "started"
    }
    save_feedback(feedback)
    print(
        "✓ Hook before_task: "
        f"{task.get('name', 'unknown')} "
        f"(rules={len(references['rules'])}, "
        f"candidates={len(references['candidates'])}, "
        f"memories={len(references['memories'])}, "
        f"graph={len(references['graph'])})"
    )
    if isinstance(runtime_result, dict):
        task_understanding = runtime_result.get("task", {})
        if isinstance(task_understanding, dict):
            for key in ("task_id", "task_type", "risk_level", "priority", "tags", "scenario", "uncertainty_level"):
                if key in task_understanding:
                    task[key] = task_understanding[key]
    return task


def _runtime_before_task_summary(runtime_result: dict | None) -> dict[str, Any]:
    """Keep feedback payload compact while preserving runtime signal."""
    if not isinstance(runtime_result, dict):
        return {}

    task_info = runtime_result.get("task", {})
    constraints = runtime_result.get("rule_constraints", {})
    return {
        "ready_to_execute": runtime_result.get("ready_to_execute"),
        "rule_description": runtime_result.get("rule_description"),
        "blocking_count": constraints.get("blocking_count") if isinstance(constraints, dict) else None,
        "task_id": task_info.get("task_id") if isinstance(task_info, dict) else None,
        "task_type": task_info.get("task_type") if isinstance(task_info, dict) else None,
        "risk_level": task_info.get("risk_level") if isinstance(task_info, dict) else None,
    }

def before_subtask(subtask):
    """Hook: Before subtask starts"""
    feedback = {
        "hook": "before_subtask",
        "subtask": subtask,
        "timestamp": datetime.now().isoformat(),
        "status": "started"
    }
    save_feedback(feedback)
    print(f"✓ Hook before_subtask: {subtask.get('name', 'unknown')}")
    return subtask

def after_subtask(subtask, result):
    """Hook: After subtask completes"""
    feedback = {
        "hook": "after_subtask",
        "subtask": subtask,
        "result": result,
        "timestamp": datetime.now().isoformat(),
        "status": "completed",
        "success": result.get("success", True)
    }
    save_feedback(feedback)
    print(f"✓ Hook after_subtask: {subtask.get('name', 'unknown')}")
    return result

def after_task(task, result):
    """Hook: After task completes - Main feedback capture point"""
    execution_steps = extract_execution_steps(task, result)
    _append_satisfaction_prompt(task, result)
    _record_conversation_memory(task, result)
    feedback = {
        "hook": "after_task",
        "task": task,
        "result": result,
        "execution_steps": execution_steps,
        "timestamp": datetime.now().isoformat(),
        "status": "completed",
        "success": result.get("success", True),
        "metrics": extract_metrics(result)
    }
    save_feedback(feedback)
    
    # Process feedback into proposals
    process_feedback(feedback)
    
    print(f"✓ Hook after_task: {task.get('name', 'unknown')}")
    return result


def _record_conversation_memory(task: dict, result: dict) -> None:
    """Persist the incoming user message into memories as a conversation entry."""
    message = str(task.get("message") or "").strip()
    if not message:
        return

    now_iso = datetime.now().isoformat()
    created_at = str(task.get("timestamp") or now_iso)
    success = bool(result.get("success", True)) if isinstance(result, dict) else True
    significance = "routine" if success else "notable"

    message_id = str(task.get("message_id") or "")
    if not message_id:
        sender = str(task.get("sender") or "unknown")
        window = created_at[:16]
        message_id = f"msg-{sha1(f'{sender}|{message}|{window}'.encode('utf-8')).hexdigest()[:16]}"

    memory_entry = {
        "id": f"conversation-{message_id}",
        "type": "conversation",
        "content": message,
        "source": str(task.get("source") or "message_handler"),
        "created_at": created_at,
        "updated_at": now_iso,
        "significance": significance,
        "metadata": {
            "message_id": message_id,
            "task_name": task.get("name"),
            "task_type": task.get("type"),
            "task_id": task.get("task_id"),
            "result_success": success,
        },
    }
    _safe_db_write(_get_memory_store().upsert_experience, memory_entry, "conversation_memory")

# ========== Feedback Storage ==========

def save_feedback(feedback):
    """Save feedback event to SQLite system_logs."""
    now_iso = datetime.now().isoformat()
    success = bool(feedback.get("success", True))
    system_log = {
        "id": f"feedback-{now_iso.replace(':', '').replace('-', '').replace('.', '')}",
        "log_type": "feedback_hook",
        "source": "feedback_system",
        "content": json.dumps(feedback, ensure_ascii=False),
        "created_at": feedback.get("timestamp") or now_iso,
        "updated_at": now_iso,
        "level": "info" if success else "warning",
        "metadata": {
            "hook": feedback.get("hook"),
            "status": feedback.get("status"),
            "success": success,
            "feedback": feedback,
        },
    }
    _safe_db_write(_get_memory_store().upsert_system_log, system_log, "feedback")
    _safe_db_write(_write_feedback_projection, feedback, "feedback_projection")


def _write_feedback_projection(feedback):
    """Project feedback into proposals(type=feedback) and reflections tables."""
    now_iso = datetime.now().isoformat()
    hook = str(feedback.get("hook") or "unknown")
    ts = str(feedback.get("timestamp") or now_iso)
    compact_ts = ts.replace(":", "").replace("-", "").replace(".", "")
    base_id = f"{hook}-{compact_ts}"

    proposal = {
        "id": f"proposal-feedback-{base_id}",
        "type": "feedback",
        "source": "feedback_system",
        "content": json.dumps(feedback, ensure_ascii=False),
        "status": "logged",
        "priority": "medium",
        "created_at": ts,
        "updated_at": now_iso,
        "metadata": {
            "hook": hook,
            "feedback_timestamp": ts,
            "success": bool(feedback.get("success", True)),
        },
    }
    _get_memory_store().upsert_proposal(proposal)

    references = feedback.get("references", {})
    reflection = {
        "id": f"reflection-feedback-{base_id}",
        "timestamp": ts,
        "trigger": f"feedback:{hook}",
        "notable_count": 1 if not feedback.get("success", True) else 0,
        "analysis": {
            "hook": hook,
            "status": feedback.get("status"),
            "success": bool(feedback.get("success", True)),
            "metrics": feedback.get("metrics", {}),
            "references_count": {
                "rules": len(references.get("rules", [])) if isinstance(references, dict) else 0,
                "candidates": len(references.get("candidates", [])) if isinstance(references, dict) else 0,
                "memories": len(references.get("memories", [])) if isinstance(references, dict) else 0,
                "graph": len(references.get("graph", [])) if isinstance(references, dict) else 0,
            },
        },
        "proposals": [proposal["id"]],
        "created_at": now_iso,
    }
    _get_memory_store().upsert_reflection(reflection)

def extract_metrics(result):
    """Extract metrics from task result"""
    return {
        "success": result.get("success", True),
        "duration_ms": result.get("duration_ms", 0),
        "tools_used": result.get("tools_used", []),
        "errors": result.get("errors", [])
    }


def extract_execution_steps(task: dict, result: dict) -> list[dict[str, Any]]:
    """Extract detailed execution steps for after_task feedback."""
    steps: list[dict[str, Any]] = []
    steps.append(
        {
            "stage": "task_received",
            "detail": task.get("name") or task.get("type") or "unknown_task",
        }
    )

    sequence_keys = ("execution_steps", "steps", "trace", "actions", "workflow")
    for key in sequence_keys:
        raw_steps = result.get(key)
        if not isinstance(raw_steps, list):
            continue
        for idx, item in enumerate(raw_steps, start=1):
            if isinstance(item, dict):
                stage = str(item.get("stage") or item.get("step") or key)
                detail = item.get("detail") or item.get("message") or item.get("action") or item
            else:
                stage = key
                detail = item
            steps.append(
                {
                    "stage": stage,
                    "index": idx,
                    "detail": str(detail),
                }
            )

    tools = result.get("tools_used", [])
    if isinstance(tools, list):
        for idx, tool in enumerate(tools, start=1):
            steps.append(
                {
                    "stage": "tool_used",
                    "index": idx,
                    "detail": str(tool),
                }
            )

    errors = result.get("errors", [])
    if isinstance(errors, list):
        for idx, error in enumerate(errors, start=1):
            steps.append(
                {
                    "stage": "error",
                    "index": idx,
                    "detail": str(error),
                }
            )

    steps.append(
        {
            "stage": "task_completed",
            "detail": f"success={bool(result.get('success', True))}",
        }
    )
    return steps


def _append_satisfaction_prompt(task: dict, result: dict) -> None:
    """Append satisfaction confirmation prompt to completion response."""
    if not isinstance(result, dict):
        return
    if SATISFACTION_PROMPT in str(result):
        return

    appended = False
    for key in ("message", "result", "response"):
        text = result.get(key)
        if isinstance(text, str) and text.strip():
            result[key] = f"{text.rstrip()}\n\n{SATISFACTION_PROMPT}"
            appended = True
            break

    if not appended:
        result["message"] = SATISFACTION_PROMPT

    result["needs_confirmation"] = True
    now_iso = datetime.now().isoformat()
    pending = {
        "active": True,
        "task_name": task.get("name"),
        "task_type": task.get("type"),
        "prompt": SATISFACTION_PROMPT,
        "created_at": now_iso,
    }
    _safe_db_write(
        lambda payload: _get_memory_store().upsert_state(CONFIRMATION_STATE_KEY, payload, now_iso),
        pending,
        "feedback_confirmation_pending",
    )


def _parse_confirmation(message: str) -> dict[str, Any]:
    text = (message or "").strip().lower()
    positive = ("满足", "满意", "可以", "是", "yes", "ok", "good", "thanks", "谢谢")
    negative = ("不满足", "不满意", "不行", "否", "no", "not", "不好", "不对", "还不行")

    if any(token in text for token in negative):
        return {"recognized": True, "satisfied": False}
    if any(token in text for token in positive):
        return {"recognized": True, "satisfied": True}
    return {"recognized": False, "satisfied": None}


def handle_user_confirmation_reply(message: str) -> dict[str, Any] | None:
    """Handle user reply to satisfaction confirmation prompt and log feedback."""
    pending = _get_memory_store().get_state(CONFIRMATION_STATE_KEY, default={})
    if not isinstance(pending, dict) or not pending.get("active"):
        return None

    parsed = _parse_confirmation(message)
    if not parsed.get("recognized"):
        return None

    now_iso = datetime.now().isoformat()
    confirmation_feedback = {
        "hook": "user_confirmation",
        "timestamp": now_iso,
        "status": "completed",
        "success": True,
        "confirmation": {
            "message": message,
            "satisfied": parsed.get("satisfied"),
            "task_name": pending.get("task_name"),
            "task_type": pending.get("task_type"),
            "prompt_created_at": pending.get("created_at"),
            "confirmed_at": now_iso,
        },
    }
    save_feedback(confirmation_feedback)

    closed_state = {
        **pending,
        "active": False,
        "response": message,
        "satisfied": parsed.get("satisfied"),
        "updated_at": now_iso,
    }
    _safe_db_write(
        lambda payload: _get_memory_store().upsert_state(CONFIRMATION_STATE_KEY, payload, now_iso),
        closed_state,
        "feedback_confirmation_closed",
    )

    # 如果不满足，记录为 notable 并触发反思
    if parsed.get("satisfied") is False:
        # 记录失败的反馈为 notable 经验
        from evoclaw.sqlite_memory import SQLiteMemoryStore
        store = SQLiteMemoryStore("memory/memory.db")
        now_iso = datetime.now().isoformat()
        
        failed_exp = {
            "id": f"feedback-failed-{now_iso.replace(':', '').replace('.', '')}",
            "type": "feedback_failure",
            "content": f"任务未满足需求: {pending.get('task_name')}",
            "source": "user_confirmation",
            "created_at": now_iso,
            "updated_at": now_iso,
            "significance": "notable",  # 标记为 notable
            "metadata": {
                "task_name": pending.get("task_name"),
                "task_type": pending.get("task_type"),
                "user_response": message,
                "reason": "用户确认需求未满足",
            }
        }
        store.upsert_experience(failed_exp)
    
    if parsed.get("satisfied"):
        return {
            "type": "feedback_confirmation",
            "success": True,
            "message": "收到，已记录你确认需求已满足。",
            "satisfied": True,
        }
    return {
        "type": "feedback_confirmation",
        "success": True,
        "message": "收到，已记录需求未满足。我会反思为什么没有满足你的需求，下次改进。",
        "satisfied": False,
    }

# ========== Proposal Processor ==========

def process_feedback(feedback):
    """Process feedback into proposals"""
    hook = feedback.get("hook")
    
    if hook == "after_task":
        # Main feedback point - generate proposal
        task = feedback.get("task", {})
        result = feedback.get("result", {})
        metrics = feedback.get("metrics", {})
        
        # Analyze feedback
        proposal = analyze_feedback(task, result, metrics)
        
        if proposal:
            save_proposal(proposal)
            print(f"  → Generated proposal: {proposal.get('type')}")
    
    elif hook == "after_subtask":
        # Subtask feedback - save for later
        pass

def analyze_feedback(task, result, metrics):
    """Analyze feedback and generate proposal"""
    success = metrics.get("success", True)
    errors = metrics.get("errors", [])
    
    if not success and errors:
        # Failure - generate improvement proposal
        return {
            "id": f"prop-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "type": "improvement",
            "source": "feedback",
            "content": f"Task '{task.get('name')}' failed: {errors[0]}",
            "task": task.get("name"),
            "errors": errors,
            "status": "pending",
            "priority": "high"
        }
    
    elif success:
        # Success - maybe generate optimization proposal
        return None  # For now, only generate on failure
    
    return None

def save_proposal(proposal):
    """Save proposal to pending queue in SQLite."""
    _safe_db_write(_get_memory_store().upsert_proposal, proposal, "proposal")

# ========== Governance Gate ==========

def governance_gate():
    """Process proposals through governance"""
    proposals = _get_memory_store().query_proposals(status="pending", limit=5000)
    if not proposals:
        return
    
    # Auto-approve (autonomous mode)
    approved = []
    for prop in proposals:
        prop["status"] = "approved"
        prop["approved_at"] = datetime.now().isoformat()
        approved.append(prop)
    
    # Save approved
    if approved:
        for p in approved:
            _safe_db_write(_get_memory_store().upsert_proposal, p, "proposal")
        print(f"✓ Governance: approved {len(approved)} proposal(s)")

# ========== Main ==========

def run_feedback_cycle():
    """Run complete feedback cycle"""
    print("\n" + "="*50)
    print("EvoClaw Feedback System")
    print("="*50)
    
    init_feedback_system()
    
    # Simulate task lifecycle with hooks
    task = {"name": "test-task", "type": "learning"}
    
    print("\n--- Task Lifecycle ---")
    before_task(task)
    
    subtask = {"name": "subtask-1", "type": "fetch"}
    before_subtask(subtask)
    after_subtask(subtask, {"success": True, "data": "ok"})
    
    result = {"success": True, "duration_ms": 1000}
    after_task(task, result)
    
    print("\n--- Governance ---")
    governance_gate()
    
    print("\n" + "="*50)
    print("Feedback cycle complete!")
    print("="*50)

if __name__ == "__main__":
    run_feedback_cycle()
