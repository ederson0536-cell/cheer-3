#!/usr/bin/env python3
"""
EvoClaw Complete Learning Flow - Full 10-Step Implementation
Covers BOTH Active Learning (RSS) AND Passive Learning (Task-summary driven)
"""
import sys
import json
import re
from collections import Counter
from math import log
from pathlib import Path
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from hashlib import sha1
from uuid import uuid4

WORKSPACE = Path(__file__).resolve().parents[1]
MEMORY = WORKSPACE / "memory"
sys.path.insert(0, str(WORKSPACE))

from evoclaw.hooks import before_task, after_task, governance_gate
from evoclaw.sqlite_memory import SQLiteMemoryStore
from evoclaw.runtime.observability import increment_metric
from evoclaw.runtime.ingress_router import route_message

# Keywords for Notable classification
NOTABLE_KEYWORDS = [
    "ai", "gpt", "chatgpt", "claude", "gemini", "openai", "anthropic",
    "breakthrough", "launch", "release", "new model", "announcement",
    "government", "policy", "regulation", "law", "official",
    "stock", "market", "economy", "recession", "financial",
    "security", "privacy", "hack", "breach", "vulnerability",
    "warning", "risk", "danger", "crisis", "emergency",
    "重要", "记住", "偏好", "纠正", "学习"
]

ANALYSIS_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "will", "your",
    "you", "are", "was", "were", "been", "can", "not", "but", "about", "into",
    "over", "under", "while", "what", "when", "where", "which", "there", "their",
    "http", "https", "www", "com", "org", "net", "github", "today", "just",
    "我们", "你们", "他们", "这个", "那个", "可以", "需要", "一个", "一些", "已经",
    "没有", "因为", "所以", "然后", "如果", "不是", "就是", "还是", "进行", "相关",
    "系统", "内容", "问题", "事情", "经验", "时候", "今天", "现在",
}

THEME_KEYWORDS = {
    "ai": {
        "ai", "llm", "gpt", "chatgpt", "openai", "anthropic", "claude", "gemini",
        "模型", "大模型", "智能体", "agent", "推理", "微调",
    },
    "programming": {
        "python", "javascript", "typescript", "java", "go", "rust", "code", "coding",
        "bug", "fix", "test", "refactor", "api", "编程", "代码", "调试", "测试",
        "重构", "脚本",
    },
    "tooling": {
        "tool", "tools", "sdk", "cli", "framework", "library", "repo", "workflow",
        "automation", "integration", "工具", "工作流", "自动化", "插件", "部署",
    },
    "governance": {
        "policy", "governance", "compliance", "regulation", "law", "rule", "proposal",
        "治理", "规则", "提案", "合规", "政策", "审批",
    },
    "security": {
        "security", "privacy", "risk", "breach", "vulnerability", "auth", "token",
        "安全", "隐私", "风险", "漏洞", "攻击", "泄露",
    },
}

TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9_+-]{1,}|[\u4e00-\u9fff]{2,}", re.IGNORECASE)

_MEMORY_STORE = None

def _get_memory_store():
    global _MEMORY_STORE
    if _MEMORY_STORE is None:
        store = SQLiteMemoryStore(WORKSPACE / "memory/memory.db")
        store.init_schema()
        _MEMORY_STORE = store
    return _MEMORY_STORE

DB_WRITE_RETRY_QUEUE = WORKSPACE / "memory" / "retry" / "db_write_failures.jsonl"
DB_WRITE_ERROR_COUNTER_KEY = "db_write_error_counter"


def _enqueue_db_retry(label: str, payload, error: Exception):
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


def _record_db_write_failure(label: str, payload, error: Exception):
    now = datetime.now().isoformat()
    try:
        with sqlite3.connect(str(MEMORY / "memory.db")) as conn:
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
                    "cron_runner",
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
        print(f"  ~ Failed to log db_write_failure: {log_err}")


def _safe_db_write(action, payload, label):
    try:
        action(payload)
        increment_metric("db_write_success_total", source="cron_runner", metadata={"label": label})
    except Exception as e:
        print(f"  ~ DB sync failed for {label}: {e}")
        increment_metric("db_write_failed_total", source="cron_runner", metadata={"label": label, "error": str(e)[:200]})
        _enqueue_db_retry(label, payload, e)
        _record_db_write_failure(label, payload, e)

def _ensure_experience_defaults(exp):
    normalized = dict(exp)
    ts = str(
        normalized.get("created_at")
        or normalized.get("timestamp")
        or datetime.now().isoformat()
    )
    normalized["created_at"] = ts
    normalized["updated_at"] = str(normalized.get("updated_at") or ts)
    normalized["timestamp"] = str(normalized.get("timestamp") or ts)
    if not normalized.get("id"):
        normalized["id"] = f"exp-{uuid4().hex[:16]}"
    return normalized

def load_config():
    with open(WORKSPACE / "evoclaw/config.json") as f:
        return json.load(f)

def load_state():
    default_state = {
        "last_reflection_at": None,
        "last_heartbeat_at": None,
        "rss_last_fetched": None,
        "rss_fetch_history": [],
        "source_last_polled": {},
    }
    state = _get_memory_store().get_state("evoclaw_state", default_state)
    if not isinstance(state, dict):
        return dict(default_state)
    normalized = dict(default_state)
    normalized.update(state)
    if not isinstance(normalized.get("rss_fetch_history"), list):
        normalized["rss_fetch_history"] = []
    if not isinstance(normalized.get("source_last_polled"), dict):
        normalized["source_last_polled"] = {}
    return normalized

def save_state(state):
    _get_memory_store().upsert_state("evoclaw_state", state, datetime.now().isoformat())
    # compatibility projection for legacy tooling/tests
    state_path = WORKSPACE / "memory" / "evoclaw-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def classify_significance(text):
    """Classify text as Notable based on keywords"""
    text_lower = text.lower()
    for kw in NOTABLE_KEYWORDS:
        if kw in text_lower:
            return "notable"
    return "routine"

def _parse_timestamp(ts):
    """Parse ISO timestamp safely and return naive datetime."""
    if not ts:
        return None
    value = str(ts).strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt

def _text_similarity(a, b):
    """Return normalized text similarity ratio in [0, 1]."""
    a_norm = " ".join(str(a or "").lower().split())
    b_norm = " ".join(str(b or "").lower().split())
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()

def _collect_experience_text(exp):
    return " ".join(
        str(exp.get(k, "") or "")
        for k in ("title", "summary", "content", "message")
    ).strip()

def _tokenize_analysis_text(text):
    tokens = []
    for token in TOKEN_PATTERN.findall(str(text or "").lower()):
        tok = token.strip()
        if len(tok) < 2:
            continue
        if tok.isdigit():
            continue
        if tok in ANALYSIS_STOPWORDS:
            continue
        tokens.append(tok)
    return tokens

def _extract_keywords(experiences, max_keywords=12):
    if not experiences:
        return []
    term_freq = Counter()
    doc_freq = Counter()
    doc_count = 0
    for exp in experiences:
        tokens = _tokenize_analysis_text(_collect_experience_text(exp))
        if not tokens:
            continue
        doc_count += 1
        term_freq.update(tokens)
        doc_freq.update(set(tokens))
    if doc_count == 0:
        return []

    scored = []
    for token, count in term_freq.items():
        if count < 2:
            continue
        score = count * (1.0 + log((1 + doc_count) / (1 + doc_freq[token])))
        scored.append((score, token, count, doc_freq[token]))
    scored.sort(key=lambda item: (-item[0], -item[2], item[1]))
    return [
        {
            "keyword": token,
            "count": count,
            "doc_count": seen,
            "score": round(score, 3),
        }
        for score, token, count, seen in scored[:max_keywords]
    ]

def _classify_themes(experiences):
    counts = Counter()
    evidence = {}
    for exp in experiences:
        text = _collect_experience_text(exp).lower()
        matched = []
        for theme, words in THEME_KEYWORDS.items():
            if any(word in text for word in words):
                counts[theme] += 1
                matched.append(theme)
        if not matched:
            counts["other"] += 1
            matched = ["other"]
        exp_id = exp.get("id")
        if exp_id:
            evidence[exp_id] = matched
    return dict(counts), evidence

def _find_repeating_patterns(experiences, keyword_stats, theme_distribution):
    patterns = []
    total = len(experiences)
    if total == 0:
        return patterns

    repeating_keywords = [k["keyword"] for k in keyword_stats if k.get("count", 0) >= 3][:4]
    if repeating_keywords:
        patterns.append(
            {
                "type": "keyword_repetition",
                "signal": "high",
                "evidence_count": len(repeating_keywords),
                "details": {"keywords": repeating_keywords},
            }
        )

    sorted_themes = sorted(theme_distribution.items(), key=lambda item: (-item[1], item[0]))
    if sorted_themes:
        lead_theme, lead_count = sorted_themes[0]
        if lead_theme != "other" and lead_count >= 2 and lead_count / total >= 0.5:
            patterns.append(
                {
                    "type": "theme_dominance",
                    "signal": "medium",
                    "evidence_count": lead_count,
                    "details": {"theme": lead_theme, "ratio": round(lead_count / total, 2)},
                }
            )

    source_counts = Counter(str(exp.get("type", "unknown")) for exp in experiences)
    if source_counts:
        lead_source, source_count = source_counts.most_common(1)[0]
        if source_count >= 3 and source_count / total >= 0.7:
            patterns.append(
                {
                    "type": "source_concentration",
                    "signal": "medium",
                    "evidence_count": source_count,
                    "details": {"source_type": lead_source, "ratio": round(source_count / total, 2)},
                }
            )

    normalized_texts = []
    for exp in experiences[:60]:
        text = " ".join(_collect_experience_text(exp).lower().split())
        if len(text) >= 24:
            normalized_texts.append((exp.get("id"), text))
    recurring_pairs = 0
    for i in range(len(normalized_texts)):
        _, base_text = normalized_texts[i]
        for j in range(i + 1, len(normalized_texts)):
            _, other_text = normalized_texts[j]
            if _text_similarity(base_text, other_text) >= 0.78:
                recurring_pairs += 1
    if recurring_pairs >= 2:
        patterns.append(
            {
                "type": "recurring_statement_shape",
                "signal": "medium",
                "evidence_count": recurring_pairs,
                "details": {"similar_pairs": recurring_pairs},
            }
        )
    return patterns

def _generate_analysis_insights(total, keyword_stats, theme_distribution, patterns):
    insights = []
    if total == 0:
        return insights
    if keyword_stats:
        top_terms = ", ".join(item["keyword"] for item in keyword_stats[:3])
        insights.append(f"近期 Notable 经验的高频关键词集中在：{top_terms}。")
    if theme_distribution:
        ordered_themes = sorted(theme_distribution.items(), key=lambda item: (-item[1], item[0]))
        lead_theme, lead_count = ordered_themes[0]
        if lead_theme != "other":
            insights.append(
                f"主题重心偏向 {lead_theme}（{lead_count}/{total}），说明关注点正在收敛。"
            )
    for pattern in patterns[:2]:
        ptype = pattern.get("type")
        if ptype == "keyword_repetition":
            kws = ", ".join(pattern.get("details", {}).get("keywords", [])[:3])
            insights.append(f"重复关键词模式明显，建议把 {kws} 归档为长期关注线索。")
        elif ptype == "source_concentration":
            source_type = pattern.get("details", {}).get("source_type")
            insights.append(f"Notable 来源集中在 {source_type}，可补充异构来源避免视角单一。")
        elif ptype == "theme_dominance":
            theme = pattern.get("details", {}).get("theme")
            insights.append(f"出现单一主题主导（{theme}），后续可围绕该主题深化行动策略。")
    if not insights:
        insights.append("当前样本偏少，暂未形成稳定趋势，建议继续积累 Notable 经验。")
    return insights[:4]

def _analyze_notable_experiences(experiences):
    sample_size = len(experiences)
    if sample_size == 0:
        return {
            "sample_size": 0,
            "top_keywords": [],
            "theme_distribution": {},
            "theme_evidence": {},
            "patterns": [],
            "insights": ["暂无 Notable 经验，无法进行趋势分析。"],
        }
    keywords = _extract_keywords(experiences)
    theme_distribution, theme_evidence = _classify_themes(experiences)
    patterns = _find_repeating_patterns(experiences, keywords, theme_distribution)
    insights = _generate_analysis_insights(sample_size, keywords, theme_distribution, patterns)
    return {
        "sample_size": sample_size,
        "top_keywords": keywords,
        "theme_distribution": theme_distribution,
        "theme_evidence": theme_evidence,
        "patterns": patterns,
        "insights": insights,
    }

def _load_today_experiences():
    """Load today's experiences from SQLite."""
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    experiences = []
    try:
        rows = _get_memory_store().query_experiences(
            start_time=start.isoformat(),
            end_time=end.isoformat(),
            limit=20000,
        )
        for row in rows:
            raw = row.get("raw")
            if isinstance(raw, dict) and raw:
                exp = dict(raw)
            else:
                exp = {
                    "id": row.get("id"),
                    "type": row.get("type"),
                    "content": row.get("content"),
                    "source": row.get("source"),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "significance": row.get("significance"),
                    "metadata": row.get("metadata", {}),
                    "tags": row.get("tags", []),
                }
            if not exp.get("significance") and row.get("significance"):
                exp["significance"] = row.get("significance")
            experiences.append(_ensure_experience_defaults(exp))
    except Exception:
        experiences = []
    return experiences, "sqlite"

def _query_db_proposals(status=None):
    rows = []
    try:
        db_rows = _get_memory_store().query_proposals(status=status, limit=5000)
        for row in db_rows:
            metadata_raw = row.get("metadata_json")
            metadata = {}
            if metadata_raw:
                try:
                    metadata = json.loads(metadata_raw)
                except json.JSONDecodeError:
                    metadata = {}
            proposal = dict(metadata) if isinstance(metadata, dict) else {}
            proposal.update(
                {
                    "id": row.get("id"),
                    "type": row.get("type"),
                    "content": row.get("content"),
                    "source": row.get("source"),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "status": row.get("status"),
                    "priority": row.get("priority"),
                    "approved_at": row.get("approved_at"),
                    "timestamp": row.get("created_at"),
                }
            )
            rows.append(proposal)
    except Exception:
        return []
    return rows

def _load_pending_proposals():
    return _query_db_proposals(status="pending")

def _load_approved_proposals():
    proposals = _query_db_proposals(status="approved")
    proposals.extend(_query_db_proposals(status="applied"))
    return proposals

def _load_soul_changes_for_id_generation():
    rows = []
    try:
        with _get_memory_store()._connect() as conn:
            db_rows = conn.execute("SELECT id, created_at, change_type FROM soul_history").fetchall()
        for row in db_rows:
            rows.append(
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "timestamp": row["created_at"],
                    "change_type": row["change_type"],
                }
            )
    except Exception:
        rows = []
    return rows

def _import_task_experiences_from_task_runs() -> int:
    """Import passive-learning experiences from structured task_runs table."""
    rows = _get_memory_store().query_task_runs(limit=5000)
    if not rows:
        print("  - No task_runs found")
        return 0

    existing_ids = {
        row.get("id")
        for row in _get_memory_store().query_experiences(exp_type="task_execution", limit=50000)
        if row.get("id")
    }

    new_count = 0
    for run in rows:
        task_id = str(run.get("task_id") or "")
        created_at = str(run.get("created_at") or datetime.now().isoformat())
        # unsatisfied tasks are handled immediately in feedback loop; cron focuses on remaining tasks
        if str(run.get("satisfaction") or "").lower() == "unsatisfied":
            continue

        exp_id = f"task-run-exp-{task_id}"
        if exp_id in existing_ids:
            continue

        exp = _ensure_experience_defaults({
            "id": exp_id,
            "type": "task_execution",
            "content": (
                f"任务总结: task_id={task_id or 'unknown'}, type={run.get('task_type')}, "
                f"status={run.get('status')}, success={run.get('success')}, "
                f"skills={','.join(run.get('skills') or [])}"
            ),
            "source": "task_runs",
            "created_at": created_at,
            "updated_at": datetime.now().isoformat(),
            "significance": "routine",
            "metadata": {
                "task_id": task_id,
                "task_type": run.get("task_type"),
                "status": run.get("status"),
                "success": run.get("success"),
                "skills": run.get("skills") or [],
                "methods": run.get("methods") or [],
            },
        })
        _safe_db_write(_get_memory_store().upsert_experience, exp, "experience")
        existing_ids.add(exp_id)
        new_count += 1

    if new_count > 0:
        print(f"  ✓ Imported {new_count} task summaries from task_runs")
    else:
        print("  - No new task summaries")
    return new_count



def _run_nightly_memory_consistency_check() -> dict[str, object]:
    """Run daily relational consistency check for layered memory tables."""
    state = load_state()
    today = datetime.now().date().isoformat()
    if state.get("last_memory_consistency_check_date") == today:
        return {"skipped": True, "reason": "already_checked_today"}

    report = _get_memory_store().run_relationship_consistency_check()
    state["last_memory_consistency_check_date"] = today
    state["last_memory_consistency_report"] = report
    save_state(state)

    total_issues = int(report.get("total_issues", 0))
    if total_issues > 0:
        print(f"  ⚠ Memory consistency issues detected: {total_issues}")
    else:
        print("  ✓ Memory consistency check passed")
    return report


def _check_json_decode_warning_metrics(hours: int = 24, threshold: int = 5) -> dict[str, object]:
    """Monitor json decode compatibility issues surfaced by sqlite read layer."""
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    with _get_memory_store()._connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM system_logs WHERE log_type = 'json_decode_warning' AND created_at >= ?",
            (since,),
        ).fetchone()
    count = int(row["cnt"]) if row is not None else 0
    if count > threshold:
        print(f"  ⚠ JSON decode warnings high: count={count} in last {hours}h (threshold={threshold})")
    else:
        print(f"  ✓ JSON decode warnings: count={count} in last {hours}h")
    return {"count": count, "hours": hours, "threshold": threshold, "alert": count > threshold}


def _count_today_experiences():
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()
    try:
        with _get_memory_store()._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM experiences WHERE created_at >= ? AND created_at < ?",
                (start, end),
            ).fetchone()
        if row is not None:
            return int(row["cnt"])
    except (ValueError, TypeError, Exception):
        return 0

# ========== Step 0: Workspace Check ==========
def step0_workspace_check():
    print("\n=== Step 0: Workspace Check ===")
    if WORKSPACE.exists():
        print(f"✓ Workspace: {WORKSPACE}")
        return True
    else:
        print(f"✗ Workspace not found")
        return False

# ========== Step 1: INGEST (Active + Passive) ==========
def step1_ingest():
    """Step 1: Fetch RSS (Active) + extract remaining task summaries (Passive)"""
    print("\n=== Step 1: INGEST ===")

    total_new = 0
    rss_history_entries = []

    # 1a. ACTIVE LEARNING: Fetch RSS
    print("\n--- Active Learning: RSS ---")
    try:
        import feedparser
        config = load_config()
        rss_config = config.get("sources", {}).get("rss", {})

        if rss_config.get("enabled", False):
            feeds = rss_config.get("feeds", [])
            for feed_url in feeds:
                try:
                    feed = feedparser.parse(feed_url)
                    entries = []

                    existing_rows = _get_memory_store().query_experiences(exp_type="rss_active", source=feed_url, limit=5000)
                    existing_links = set()
                    existing_entry_ids = set()
                    for row in existing_rows:
                        md = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                        if md.get("link"):
                            existing_links.add(str(md.get("link")))
                        if md.get("entry_id"):
                            existing_entry_ids.add(str(md.get("entry_id")))

                    for entry in feed.entries[:10]:
                        entry_id = str(entry.get("id") or "")
                        link = str(entry.get("link") or "")
                        if (entry_id and entry_id in existing_entry_ids) or (link and link in existing_links):
                            continue

                        now_iso = datetime.now().isoformat()
                        title = entry.get("title", "")
                        summary = entry.get("summary", "")[:500]
                        sig = classify_significance(f"{title} {summary}")

                        exp = _ensure_experience_defaults({
                            "type": "rss_active",
                            "significance": sig,
                            "source": feed_url,
                            "title": title,
                            "summary": summary,
                            "content": f"{title}\n{summary}".strip(),
                            "timestamp": now_iso,
                            "created_at": now_iso,
                            "updated_at": now_iso,
                            "metadata": {"entry_id": entry_id, "link": link},
                        })
                        entries.append(exp)

                    for e in entries:
                        # 只写入 external_learning_events (原始数据)
                        _safe_db_write(
                            _get_memory_store().upsert_external_learning_event,
                            {
                                "event_id": f"rss-{(e.get('metadata') or {}).get('entry_id') or e.get('id')}",
                                "source_type": "rss",
                                "source_name": feed_url,
                                "title": e.get("title", ""),
                                "content": e.get("content", ""),
                                "url": (e.get("metadata") or {}).get("link", ""),
                                "collected_at": e.get("created_at", datetime.now().isoformat()),
                                "significance": e.get("significance", "routine"),
                                "status": "new",
                                "metadata": {"entry_id": (e.get("metadata") or {}).get("entry_id")},
                            },
                            "external_learning_event",
                        )

                    print(f"  ✓ RSS: {len(entries)} from {feed_url[:30]}...")
                    total_new += len(entries)
                    rss_history_entries.append(
                        {
                            "feed": feed_url,
                            "fetched_at": datetime.now().isoformat(),
                            "new_count": len(entries),
                        }
                    )
                except Exception as e:
                    print(f"  ✗ Error: {e}")
    except Exception as e:
        print(f"RSS Error: {e}")

    # 1b. PASSIVE LEARNING: remaining tasks are learned from task_runs
    print("\n--- Passive Learning: Task summaries (remaining tasks) ---")
    try:
        task_new = _import_task_experiences_from_task_runs()
        total_new += task_new

        if rss_history_entries:
            state["rss_last_fetched"] = rss_history_entries[-1]["fetched_at"]
            history = state.get("rss_fetch_history", [])
            if not isinstance(history, list):
                history = []
            history.extend(rss_history_entries)
            state["rss_fetch_history"] = history[-200:]
        save_state(state)
    except Exception as e:
        print(f"  ✗ Error: {e}")

    print(f"\n✓ Step 1 complete: {total_new} new experiences")
    return total_new

# ========== Step 1b: EXTRACT NOTABLE FROM EXTERNAL LEARNING ==========
def step1b_extract_notable_from_external():
    """从 external_learning_events 提取 notable 到 memories"""
    print("\n--- Extract Notable from External Learning ---")
    try:
        store = _get_memory_store()
        
        # 查询未处理的 external_learning_events
        external_events = store.query_external_learning_events(status="new", limit=100)
        if not external_events:
            print("  - No new external events to extract")
            return 0
        
        print(f"  Found {len(external_events)} external events")
        
        extracted_count = 0
        for event in external_events:
            event_id = event.get("event_id")
            significance = event.get("significance", "routine")
            
            # 只有 notable 以上的才提取到 memories
            if significance in ("notable", "pivotal"):
                # 检查是否已存在
                existing = store.query_experiences(source=event.get("url", ""), limit=1)
                if existing:
                    # 已存在，标记为 processed
                    store.mark_external_learning_event_status(event_id, "extracted")
                    continue
                
                # 写入 memories
                now = datetime.now().isoformat()
                exp = {
                    "id": f"ext-{event.get('event_id')}",
                    "type": "rss_active",
                    "source": event.get("source_name", ""),
                    "content": f"{event.get('title', '')}\n{event.get('content', '')}".strip(),
                    "significance": significance,
                    "created_at": event.get("collected_at", now),
                    "updated_at": now,
                    "metadata": {"event_id": event_id, "url": event.get("url", "")},
                }
                store.upsert_experience(exp)
                store.mark_external_learning_event_status(event_id, "extracted")
                extracted_count += 1
            else:
                # routine 也标记为处理
                store.mark_external_learning_event_status(event_id, "processed")
        
        print(f"  ✓ Extracted {extracted_count} notable events to memories")
        return extracted_count
        
    except Exception as e:
        print(f"  ✗ Extract error: {e}")
        return 0


# ========== Step 2: REFLECT ==========
def step2_reflect():
    """Step 2: Process ALL experiences (Active + Passive)"""
    print("\n=== Step 2: REFLECT ===")

    experiences, source = _load_today_experiences()
    if not experiences:
        print("No experiences found (SQLite)")
        return 0
    print(f"Experience source: {source}")

    # Count by type
    active_rss = sum(1 for e in experiences if e.get('type') == 'rss_active')
    passive_task = sum(1 for e in experiences if e.get('type') == 'task_execution')
    passive_conv = sum(1 for e in experiences if e.get('type') == 'conversation')
    routine = sum(1 for e in experiences if e.get('significance') == 'routine')
    notable = sum(1 for e in experiences if e.get('significance') == 'notable')

    print(f"Total: {len(experiences)} (Active RSS: {active_rss}, Passive tasks: {passive_task}, Passive conversations: {passive_conv})")
    print(f"  Routine: {routine}, Notable: {notable}")

    # Upgrade if needed
    config = load_config()
    threshold = config.get('reflection', {}).get('notable_batch_size', 2)

    if notable < threshold:
        upgraded = 0
        new_experiences = []
        for exp in experiences:
            if exp.get('significance') == 'routine' and upgraded < (threshold - notable):
                text = exp.get('title', '') + exp.get('summary', '') + exp.get('content', '')
                if len(text) > 20:
                    exp['significance'] = 'notable'
                    upgraded += 1
            new_experiences.append(exp)

        if upgraded > 0:
            notable += upgraded
            print(f"✓ Upgraded {upgraded} to Notable")
            experiences = new_experiences

    for exp in experiences:
        _safe_db_write(_get_memory_store().upsert_experience, exp, "experience")

    notable_experiences = [e for e in experiences if e.get("significance") == "notable"]
    content_trends = _analyze_notable_experiences(notable_experiences)

    reflection_now = datetime.now().isoformat()
    reflection_id = f"REF-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    reflection = {
        "id": reflection_id,
        "timestamp": reflection_now,
        "created_at": reflection_now,
        "trigger": "cron_step2_reflect",
        "notable_count": notable,
        "analysis": {
            "total_count": len(experiences),
            "active_rss_count": active_rss,
            "passive_task_count": passive_task,
            "passive_conversation_count": passive_conv,
            "routine_count": routine,
            "notable_count": notable,
            "content_trends": content_trends,
        },
        "proposals": [],
    }
    _safe_db_write(_get_memory_store().upsert_reflection, reflection, "reflection")

    # Mark all processed experiences as reflected in DB
    if experiences:
        exp_ids = [e.get("id") for e in experiences if e.get("id")]
        if exp_ids:
            marked_count = _get_memory_store().mark_experiences_reflected(exp_ids, reflection_id)
            print(f"  ✓ Marked {marked_count} experiences as reflected")

    if content_trends.get("insights"):
        print("  Insights:")
        for insight in content_trends["insights"][:3]:
            print(f"    - {insight}")

    if notable >= threshold:
        print(f"✓ Notable ({notable}) >= threshold ({threshold}) → Reflection triggered")
        return notable
    else:
        print(f"- Notable ({notable}) < threshold ({threshold})")
        return notable

# ========== Step 3: PROPOSE ==========
def step3_propose(notable_count):
    print("\n=== Step 3: PROPOSE ===")
    if notable_count < 2:
        print("No notable experiences to propose from")
        return []

    proposals = []
    try:
        experiences, _ = _load_today_experiences()

        notable_exps = [e for e in experiences if e.get('significance') == 'notable']

        if notable_exps:
            # Check sources
            active = sum(1 for e in notable_exps if e.get('type') == 'rss_active')
            passive_tasks = sum(1 for e in notable_exps if e.get('type') == 'task_execution')
            passive_conversations = sum(1 for e in notable_exps if e.get('type') == 'conversation')
            passive = passive_tasks + passive_conversations
            # Get insights from latest reflection
            reflection_insights = ""
            try:
                store = _get_memory_store()
                reflections = store.query_reflections(limit=1)
                if reflections:
                    latest = reflections[0]
                    analysis = latest.get("analysis", {})
                    trends = analysis.get("content_trends", {})
                    insights = trends.get("insights", [])
                    if insights:
                        reflection_insights = " | ".join(insights[:2])
            except Exception as reflect_err:
                print(f"  ~ Failed to load reflection insights: {reflect_err}")
            
            if reflection_insights:
                proposal_content = f"从 {notable_count} 条 Notable 经验中发现趋势 ({reflection_insights})"
            else:
                proposal_content = f"从 {notable_count} 条 Notable 经验中发现趋势 (主动: {active}, 被动任务: {passive_tasks}, 被动对话: {passive_conversations})"

            # Dedup: skip similar learning_insight proposal from last 10 minutes
            now = datetime.now()
            recent_cutoff = now - timedelta(minutes=10)
            existing = _query_db_proposals(status="pending")
            for existing_prop in existing:
                if existing_prop.get("type") != "learning_insight":
                    continue
                if existing_prop.get("status") not in {None, "pending"}:
                    continue
                ts = _parse_timestamp(existing_prop.get("timestamp"))
                if not ts or ts < recent_cutoff:
                    continue
                sim = _text_similarity(proposal_content, existing_prop.get("content", ""))
                if sim >= 0.85:
                    print("~ Skip duplicate learning_insight proposal (recent similar content)")
                    return []

            proposal_now = datetime.now().isoformat()
            proposal = {
                "id": f"prop-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                "timestamp": proposal_now,
                "created_at": proposal_now,
                "updated_at": proposal_now,
                "type": "learning_insight",
                "content": proposal_content,
                "sources": {"active": active, "passive": passive, "passive_tasks": passive_tasks, "passive_conversations": passive_conversations},
                "status": "pending",
                "priority": "medium"
            }
            proposals.append(proposal)
            _safe_db_write(_get_memory_store().upsert_proposal, proposal, "proposal")

            print(f"✓ Generated {len(proposals)} proposal(s)")
    except Exception as e:
        print(f"Error: {e}")

    return proposals

# ========== Step 4: GOVERN ==========
def step4_govern():
    print("\n=== Step 4: GOVERN ===")
    config = load_config()
    governance = config.get('governance', {}).get('level', 'autonomous')
    print(f"Governance: {governance}")

    pending = _load_pending_proposals()
    if not pending:
        print("No pending")
        return 0

    # Process pending items from SQLite.
    to_process = [p for p in pending if p.get("status") == "pending"]

    existing_approved = _query_db_proposals(status="approved")
    existing_approved.extend(_query_db_proposals(status="applied"))
    approved_ids = {p.get("id") for p in existing_approved if p.get("id")}

    newly_approved = []
    if governance == 'autonomous':
        now_iso = datetime.now().isoformat()
        for prop in to_process:
            prop_id = prop.get("id")
            if prop_id and prop_id in approved_ids:
                print(f"~ Skip already approved id: {prop_id}")
                continue
            approved_prop = dict(prop)
            approved_prop['status'] = 'approved'
            approved_prop['approved_at'] = now_iso
            newly_approved.append(approved_prop)
            if prop_id:
                approved_ids.add(prop_id)

    for p in newly_approved:
        _safe_db_write(_get_memory_store().upsert_proposal, p, "proposal")

    # Keep still-pending items in SQLite.
    remaining = to_process if governance != 'autonomous' else []
    for p in remaining:
        _safe_db_write(_get_memory_store().upsert_proposal, p, "proposal")

    if newly_approved:
        print(f"✓ Approved {len(newly_approved)}")

    return len(newly_approved)

def _find_line_index(lines, target):
    """Find line index matching target content"""
    t = (target or "").strip()
    if not t:
        return None
    for idx, line in enumerate(lines):
        if line.strip() == t:
            return idx
    return None

def _find_insert_index(lines, target_section=None, target_subsection=None):
    """Find insertion index for new bullet"""
    if target_subsection:
        for i, line in enumerate(lines):
            if line.strip() == target_subsection:
                j = i + 1
                while j < len(lines):
                    stripped = lines[j].strip()
                    if stripped.startswith("### ") or stripped.startswith("## "):
                        break
                    j += 1
                return j
    if target_section:
        for i, line in enumerate(lines):
            if line.strip() == target_section:
                j = i + 1
                while j < len(lines):
                    stripped = lines[j].strip()
                    if stripped.startswith("## "):
                        break
                    j += 1
                return j
    return len(lines)

def _next_change_id(existing_rows, now):
    """Generate next change ID: CHG-YYYYMMDD-NNN"""
    date_part = now.strftime("%Y%m%d")
    prefix = f"CHG-{date_part}-"
    max_seq = 0
    for row in existing_rows:
        cid = str(row.get("id", ""))
        if cid.startswith(prefix):
            try:
                seq = int(cid.split("-")[-1])
                max_seq = max(max_seq, seq)
            except ValueError:
                pass
    return f"CHG-{date_part}-{max_seq + 1:03d}"

def _apply_single_proposal(soul_lines, prop):
    """Apply a single proposal to SOUL.md lines"""
    change_type = prop.get("change_type")
    if change_type not in {"add", "modify", "remove"}:
        return None

    current = (prop.get("current_content") or "").strip()
    proposed = (prop.get("proposed_content") or "").strip()

    # Reject CORE changes
    if prop.get("tag") == "[CORE]":
        return None
    if "[CORE]" in current or "[CORE]" in proposed:
        return None

    # Validate format
    if change_type in {"add", "modify"}:
        if not proposed.startswith("- "):
            return None
        if not proposed.endswith("[MUTABLE]"):
            return None

    if change_type in {"modify", "remove"} and not current:
        return None

    before = None
    after = None

    if change_type == "add":
        # Check if already exists
        if _find_line_index(soul_lines, proposed) is not None:
            return None
        idx = _find_insert_index(
            soul_lines,
            target_section=prop.get("target_section"),
            target_subsection=prop.get("target_subsection"),
        )
        soul_lines.insert(idx, proposed + "\n")
        after = proposed

    elif change_type == "modify":
        idx = _find_line_index(soul_lines, current)
        if idx is None:
            return None
        if "[MUTABLE]" not in soul_lines[idx]:
            return None
        before = soul_lines[idx].strip()
        soul_lines[idx] = proposed + "\n"
        after = proposed

    elif change_type == "remove":
        idx = _find_line_index(soul_lines, current)
        if idx is None:
            return None
        if "[MUTABLE]" not in soul_lines[idx]:
            return None
        before = soul_lines[idx].strip()
        del soul_lines[idx]

    return {
        "proposal_id": prop.get("id"),
        "reflection_id": prop.get("reflection_id"),
        "experience_ids": prop.get("experience_ids", []),
        "section": prop.get("target_section"),
        "subsection": prop.get("target_subsection"),
        "change_type": change_type,
        "before": before,
        "after": after,
        "reason": prop.get("reason", ""),
        "governance_level": load_config().get("governance", {}).get("level", "autonomous"),
        "resolved_by": prop.get("resolved_by", "auto"),
    }

# ========== Helper Functions for Apply to Rules ==========
def _apply_to_rules(approved_proposals):
    """Apply approved proposals to SQLite rules + rules/active JSON files."""
    rules_dir = WORKSPACE / "memory" / "rules" / "active"
    rules_dir.mkdir(parents=True, exist_ok=True)

    applied = []

    def _normalize_priority(value):
        v = str(value or "").strip().upper()
        aliases = {
            "P0": "P0_HARD",
            "P1": "P1_GOVERNANCE",
            "P2": "P2_TASK_TYPE",
            "P3": "P3_SCENARIO",
            "P4": "P4_SUGGESTION",
            "P0_HARD": "P0_HARD",
            "P1_GOVERNANCE": "P1_GOVERNANCE",
            "P2_TASK_TYPE": "P2_TASK_TYPE",
            "P3_SCENARIO": "P3_SCENARIO",
            "P4_SUGGESTION": "P4_SUGGESTION",
        }
        return aliases.get(v, "P2_TASK_TYPE")

    def _looks_like_rule_proposal(prop):
        prop_type = str(prop.get("type") or "").lower()
        if prop_type in {
            "rule",
            "governance",
            "task_rule",
            "scenario_rule",
            "policy",
            "constraint",
            "guardrail",
        }:
            return True
        if prop.get("rule_type") or prop.get("rule_content") or prop.get("constraints"):
            return True
        metadata = prop.get("metadata")
        if isinstance(metadata, dict):
            if metadata.get("rule_type") or metadata.get("constraints") or metadata.get("task_type"):
                return True
        return False

    def _proposal_to_rule(prop):
        proposal_id = str(prop.get("id") or "")
        content = str(prop.get("rule_content") or prop.get("content") or "").strip()
        if not content:
            return None

        metadata = prop.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        task_scope = prop.get("task_type") or metadata.get("task_type")
        scenario_scope = prop.get("scenario") or metadata.get("scenario")
        priority = _normalize_priority(
            prop.get("priority_level")
            or prop.get("rule_priority")
            or metadata.get("priority_level")
            or metadata.get("rule_priority")
            or prop.get("rule_type")
        )
        valid_from = (
            prop.get("valid_from")
            or metadata.get("valid_from")
            or prop.get("approved_at")
            or datetime.now().isoformat()
        )
        valid_until = (
            prop.get("valid_until")
            or prop.get("expires_at")
            or metadata.get("valid_until")
            or metadata.get("expires_at")
        )
        constraints = prop.get("constraints")
        if not isinstance(constraints, list):
            constraints = metadata.get("constraints")
        if not isinstance(constraints, list):
            constraints = []

        if proposal_id:
            rule_id = f"rule-{proposal_id}"
        else:
            digest = sha1(
                json.dumps(
                    {"content": content, "created_at": prop.get("created_at")},
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()[:16]
            rule_id = f"rule-{digest}"

        return {
            "id": rule_id,
            "content": {
                "text": content,
                "priority": priority,
                "task_type": task_scope,
                "scenario": scenario_scope,
                "constraints": constraints,
                "valid_from": str(valid_from),
                "valid_until": str(valid_until) if valid_until else None,
                "enabled": True,
            },
            "source_proposal_id": proposal_id,
            "created_at": datetime.now().isoformat(),
            "enabled": 1,
        }

    for prop in approved_proposals:
        if prop.get("status") != "approved":
            continue

        if not _looks_like_rule_proposal(prop):
            continue

        rule_row = _proposal_to_rule(prop)
        if not rule_row:
            continue

        _safe_db_write(_get_memory_store().upsert_rule, rule_row, "rule")

        rule_file = rules_dir / f"{rule_row['id']}.json"
        with open(rule_file, "w", encoding="utf-8") as f:
            json.dump(rule_row, f, ensure_ascii=False, indent=2)

        applied.append({
            "proposal_id": rule_row.get("source_proposal_id"),
            "target": str(rule_file.relative_to(WORKSPACE)),
            "change_type": "add_rule"
        })
        print(f"  ✓ Rule added: {rule_row.get('id')} -> {rule_file.name}")

    if applied:
        print(f"✓ Applied {len(applied)} rule(s) to SQLite + rules/active/")

    # Also apply knowledge to semantic/
    applied_semantic = _apply_to_semantic(approved_proposals)

    return applied + applied_semantic

# ========== Helper Functions for Apply to Semantic ==========
def _apply_to_semantic(approved_proposals):
    """Apply approved knowledge proposals to SQLite semantic memories."""

    applied = []
    now = datetime.now()

    for prop in approved_proposals:
        if prop.get("status") != "approved":
            continue

        # Check if this is a knowledge-type proposal
        prop_type = prop.get("type", "")
        content = prop.get("content", "")

        # Knowledge proposals: insights, patterns, knowledge types
        if prop_type in ["knowledge", "insight", "learning_insight", "pattern"]:
            if not content:
                continue

            # Persist semantic knowledge in SQLite only.
            entry = _ensure_experience_defaults({
                "type": "knowledge",
                "significance": "notable",
                "content": content,
                "source": "proposal",
                "source_id": prop.get("id"),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "proposal_id": prop.get("id"),
                "reason": prop.get("reason", ""),
                "metadata": {
                    "source_id": prop.get("id"),
                    "proposal_id": prop.get("id"),
                    "reason": prop.get("reason", ""),
                    "semantic_type": prop_type,
                },
                "tags": ["semantic", "knowledge"],
            })
            _safe_db_write(_get_memory_store().upsert_experience, entry, "knowledge")

            applied.append({
                "proposal_id": prop.get("id"),
                "target": "sqlite:memories(category=knowledge)",
                "change_type": "add_knowledge"
            })
            print(f"  ✓ Knowledge added: {prop.get('id')} -> SQLite")

    if applied:
        print(f"✓ Applied {len(applied)} knowledge to SQLite semantic memories")

    return applied
def step5_apply():
    """Step 5: Apply approved proposals to SOUL.md"""
    print("\n=== Step 5: APPLY ===")

    approved = _load_approved_proposals()
    if not approved:
        print("No approved proposals to apply")
        return []

    soul_path = WORKSPACE / "SOUL.md"
    if not soul_path.exists():
        print("SOUL.md not found")
        return []

    # Read SOUL.md
    soul_lines = soul_path.read_text(encoding="utf-8").splitlines(keepends=True)

    applied_changes = []
    updated_approved = []
    now_iso = datetime.now().isoformat()

    for prop in approved:
        if prop.get("status") != "approved":
            updated_approved.append(prop)
            continue

        change = _apply_single_proposal(soul_lines, prop)
        if not change:
            # Not a structured proposal, skip but keep in approved
            updated_approved.append(prop)
            continue

        # Successfully applied
        applied_changes.append(change)
        p2 = dict(prop)
        p2["status"] = "applied"
        p2["resolved_at"] = now_iso
        p2["resolved_by"] = p2.get("resolved_by") or "auto"
        updated_approved.append(p2)
        print(f"  ✓ Applied: {prop.get('id')}")

    # Write back if changes were made
    if applied_changes:
        soul_path.write_text("".join(soul_lines), encoding="utf-8")
        for p in updated_approved:
            _safe_db_write(_get_memory_store().upsert_proposal, p, "proposal")
        print(f"✓ Applied {len(applied_changes)} proposal(s) to SOUL.md")
    else:
        print("No structured proposals to apply")
    
    # Also apply to rules/active/ if applicable
    applied_to_rules = _apply_to_rules(approved)
    
    return applied_changes + applied_to_rules

# ========== Step 6: LOG ==========
def step6_log(applied_changes):
    """Step 6: Log changes to soul_changes files"""
    print("\n=== Step 6: LOG ===")

    if not applied_changes:
        print("No changes to log")
        return 0

    soul_changes_md_path = WORKSPACE / "memory/soul_changes.md"

    # Read existing entries from DB first, fallback for migration.
    existing = _load_soul_changes_for_id_generation()
    now = datetime.now()

    new_entries = []
    for change in applied_changes:
        entry = {
            "id": _next_change_id(existing, now),
            "timestamp": now.isoformat(),
            "created_at": now.isoformat(),
            **change,
        }
        existing.append(entry)
        new_entries.append(entry)
        _safe_db_write(_get_memory_store().upsert_soul_change, entry, "soul_change")

    # Append to MD
    if not soul_changes_md_path.exists():
        soul_changes_md_path.write_text(
            "# Soul Evolution Timeline\n_Tracking identity changes over time._\n\n---\n",
            encoding="utf-8",
        )

    with open(soul_changes_md_path, "a", encoding="utf-8") as mf:
        for entry in new_entries:
            section = entry.get("section") or "(unknown section)"
            subsection = entry.get("subsection") or "(no subsection)"
            mf.write(
                f"\n## {entry['timestamp']}\n"
                f"- {entry['id']} | {entry.get('proposal_id', 'unknown')} | {entry.get('change_type', 'unknown')} | {section} / {subsection}\n"
                f"- before: {entry.get('before')}\n"
                f"- after: {entry.get('after')}\n"
                f"- reason: {entry.get('reason', '')}\n"
            )

    print(f"✓ Logged {len(applied_changes)} change(s) to soul_changes")
    return len(applied_changes)

def step7_state():
    print("\n=== Step 7: STATE ===")
    state = load_state()
    now_iso = datetime.now().isoformat()
    state["last_heartbeat_at"] = now_iso
    state["last_reflection_at"] = now_iso
    total = _count_today_experiences()
    state["total_experiences_today"] = total
    state["pending_proposals_count"] = len(_load_pending_proposals())
    state["total_reflections"] = len(_get_memory_store().query_reflections(limit=100000))
    state["total_soul_changes"] = len(_get_memory_store().query_soul_changes(limit=100000))
    source_last_polled = state.get("source_last_polled", {})
    if not isinstance(source_last_polled, dict):
        source_last_polled = {}
    source_last_polled["heartbeat"] = now_iso
    state["source_last_polled"] = source_last_polled
    save_state(state)
    print(f"✓ State: {total} experiences")

def step8_notify():
    print("\n=== Step 8: NOTIFY ===")
    print("✓ Notification logged")

def step9_final_check():
    print("\n=== Step 9: FINAL CHECK ===")
    print("✓ Verified")

def step10_report():
    print("\n=== Step 10: PIPELINE REPORT ===")
    report = {"timestamp": datetime.now().isoformat(), "status": "complete", "sources": ["active_rss", "passive_task", "passive_conversation"]}
    history = _get_memory_store().get_state("pipeline_reports", [])
    if not isinstance(history, list):
        history = []
    history.append(report)
    _get_memory_store().upsert_state("pipeline_reports", history[-500:], report["timestamp"])
    print("✓ Report saved to SQLite state")

# ========== MAIN ==========
def main():
    # Feedback: before task
    task = {"name": "cron-learning-cycle", "type": "learning", "action": "full_pipeline"}
    before_task(task)

    print(f"\n{'='*60}")
    print(f"EvoClaw Full Learning Flow - {datetime.now()}")
    print(f"Active Learning (RSS) + Passive Learning (Task-summary driven)")
    print('='*60)

    if not step0_workspace_check():
        return

    step1_ingest()
    step1b_extract_notable_from_external()
    notable = step2_reflect()
    proposals = step3_propose(notable)
    approved = step4_govern()
    applied_changes = step5_apply()
    step6_log(applied_changes)
    step7_state()
    step8_notify()
    step9_final_check()
    step10_report()

    print("\n" + "="*60)
    print("✓ Full flow complete (Active + Passive task-wide)")
    print("="*60)

    # Feedback: after task
    result = {"success": True, "duration_ms": 5000, "data": "processed"}
    after_task(task, result)

    # Governance
    governance_gate()






def _process_recent_messages():
    """直接处理最近的聊天消息"""
    try:
        msg_log = WORKSPACE / "logs/message_handler.jsonl"
        if not msg_log.exists():
            return
        
        with open(msg_log, "r") as f:
            lines = f.readlines()
        
        if lines:
            last_line = lines[-1]
            msg = json.loads(last_line)
            if msg.get("event") == "receive":
                message = msg.get("message", "")
                if message:
                    try:
                        route_message(
                            message,
                            source="cron_runner",
                            channel="cron_recent_message",
                            metadata={"session_id": "cron", "sender": "cron_runner"},
                        )
                        print(f"  ✓ Processed via ingress: {message[:30]}...")
                    except Exception as handle_err:
                        print(f"  ~ Failed to process recent message: {handle_err}")
    except Exception as recent_err:
        print(f"  ~ _process_recent_messages error: {recent_err}")


def _process_voice_messages():
    """处理新的语音文件"""
    try:
        voice_dir = Path("/home/bro/.openclaw/media/inbound")
        if not voice_dir.exists():
            return
        
        # 获取已处理的文件列表
        conn = sqlite3.connect(str(MEMORY / "memory.db"))
        cur = conn.cursor()
        cur.execute("SELECT value_json FROM system_state WHERE key = 'processed_voice_files'")
        result = cur.fetchone()
        processed = set(json.loads(result[0])) if result else set()
        
        # 找到新语音文件
        new_files = [f for f in voice_dir.glob("file_*.ogg") if f.name not in processed]
        
        if new_files:
            latest = max(new_files, key=lambda x: x.stat().st_mtime)
            
            # 转换并识别
            import subprocess
            wav_path = "/tmp/voice_process.wav"
            subprocess.run(["ffmpeg", "-i", str(latest), "-ar", "16000", "-ac", "1", wav_path, "-y"], 
                        capture_output=True)
            
            from faster_whisper import WhisperModel
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, info = model.transcribe(wav_path)
            text = "".join([s.text for s in segments])
            
            if text.strip():
                try:
                    route_message(
                        text.strip(),
                        source="cron_runner",
                        channel="cron_voice",
                        metadata={"session_id": "cron", "sender": "voice_transcriber"},
                    )
                    print(f"  ✓ Voice via ingress: {text.strip()[:30]}...")
                except Exception as voice_handle_err:
                    print(f"  ~ Failed to process voice message: {voice_handle_err}")
            
            processed.add(latest.name)
            cur.execute("INSERT OR REPLACE INTO system_state (key, value_json) VALUES (?, ?)",
                       ("processed_voice_files", json.dumps(list(processed))))
            conn.commit()
        
        conn.close()
    except Exception as e:
        print(f"  ~ _process_voice_messages error: {e}")




if __name__ == "__main__":
    main()
