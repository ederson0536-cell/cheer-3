#!/usr/bin/env python3
"""
Unified Memory Retrieval
Track A: rules retrieval
Track B: experience retrieval
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from typing import Any, Dict, List

from components.candidate_memory import get_candidate_memory
from components.experience_recall import get_experience_recall
from components.governance import GovernanceGate
from components.graph_memory import get_graph_memory
from components.rule_engine import get_rule_engine
from components.semantic_search import search_similar

WORKSPACE = resolve_workspace(__file__)


class MemoryRetrieval:
    """Unified retrieval across rules and memory tracks."""

    def __init__(self):
        self.rule_engine = get_rule_engine()
        self.experience_recall = get_experience_recall()
        self.governance_gate = GovernanceGate()
        self.candidate_memory = get_candidate_memory()
        self.graph_memory = get_graph_memory()
        self.memory_db = WORKSPACE / "memory" / "memory.db"

        self.stats_file = WORKSPACE / "memory" / "retrieval" / "stats.json"
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        self.stats = self._load_stats()

    def _load_stats(self) -> Dict[str, Any]:
        if self.stats_file.exists():
            try:
                with open(self.stats_file) as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "total_calls": 0,
            "updated_at": None,
            "tracks": {
                "rules": {"hit": 0, "miss": 0},
                "episodic": {"hit": 0, "miss": 0},
                "semantic": {"hit": 0, "miss": 0},
                "memories": {"hit": 0, "miss": 0},
                "candidate": {"hit": 0, "miss": 0},
                "graph": {"hit": 0, "miss": 0},
            },
        }

    def _persist_stats(self):
        self.stats["updated_at"] = datetime.now().isoformat()
        with open(self.stats_file, "w") as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)

    def _update_track_stat(self, track: str, hit: bool):
        key = "hit" if hit else "miss"
        self.stats["tracks"].setdefault(track, {"hit": 0, "miss": 0})
        self.stats["tracks"][track][key] += 1

    def retrieve_rules(self, task_understanding: Dict[str, Any]) -> Dict[str, Any]:
        """Track A: retrieve rules (rules, governance, task-type, scenario)."""

        task_type = task_understanding.get("task_type", "conversation")
        scenario = task_understanding.get("scenario", "")
        risk_level = task_understanding.get("risk_level", "low")

        rules = self.rule_engine.get_rules_for_task(
            task_type=task_type,
            risk_level=risk_level,
            scenario=scenario,
        )

        governance = {
            "level": self.governance_gate.config.get("governance_level"),
            "auto_approve_categories": self.governance_gate.config.get(
                "auto_approve_categories", []
            ),
            "auto_approve_min_confidence": self.governance_gate.config.get(
                "auto_approve_min_confidence"
            ),
        }

        return {
            "task_type": task_type,
            "scenario": scenario,
            "risk_level": risk_level,
            "rules": rules,
            "governance": governance,
        }

    def _match_candidate(
        self, candidate: Dict[str, Any], task_type: str, scenario: str, tags: List[str]
    ) -> bool:
        text = " ".join(
            [
                str(candidate.get("skill_id", "")),
                str(candidate.get("task_type", "")),
                str(candidate.get("knowledge", "")),
                str(candidate.get("source", "")),
                str(candidate.get("context", "")),
            ]
        ).lower()

        checks = [task_type, scenario] + list(tags or [])
        checks = [c.lower() for c in checks if c]
        return any(token in text for token in checks)

    def _search_memories_fts(self, message: str, task_understanding: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        if not self.memory_db.exists():
            return []

        task_type = str(task_understanding.get("task_type") or "")
        scenario = str(task_understanding.get("scenario") or "")
        tags = task_understanding.get("tags") or []
        if not isinstance(tags, list):
            tags = []

        tokens = [message, task_type, scenario] + [str(t) for t in tags]
        query_terms = []
        for token in tokens:
            for piece in str(token).strip().split():
                piece = piece.strip().lower()
                if len(piece) >= 2:
                    query_terms.append(piece)

        # Keep query small and focused for FTS5.
        query_terms = list(dict.fromkeys(query_terms))[:8]
        if not query_terms:
            return []

        match_query = " OR ".join(query_terms)
        sql = """
            SELECT
                m.id, m.type, m.content, m.source, m.created_at, m.significance,
                bm25(memories_fts) AS score
            FROM memories_fts
            JOIN memories AS m ON m.rowid = memories_fts.rowid
            WHERE memories_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """

        try:
            with sqlite3.connect(self.memory_db) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(sql, (match_query, limit)).fetchall()
        except Exception:
            return []

        results = []
        for row in rows:
            results.append(
                {
                    "id": row["id"],
                    "type": row["type"],
                    "content": row["content"],
                    "source": row["source"],
                    "timestamp": row["created_at"],
                    "significance": row["significance"],
                    "score": round(float(row["score"]), 4),
                }
            )
        return results

    def _search_graph_sqlite(self, task_understanding: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        if not self.memory_db.exists():
            return []

        task_type = str(task_understanding.get("task_type") or "").lower()
        scenario = str(task_understanding.get("scenario") or "").lower()
        tags = [str(t).lower() for t in task_understanding.get("tags", []) if t]
        terms = [t for t in [task_type, scenario] + tags if t]
        if not terms:
            return []

        like_clauses = []
        params: List[Any] = []
        for term in terms[:8]:
            pattern = f"%{term}%"
            like_clauses.append("(LOWER(ge.entity_type) LIKE ? OR LOWER(COALESCE(ge.name, '')) LIKE ? OR LOWER(ge.properties_json) LIKE ?)")
            params.extend([pattern, pattern, pattern])

        where = " OR ".join(like_clauses)
        sql = f"""
            SELECT
                ge.id AS entity_id,
                ge.entity_type,
                COALESCE(ge.name, '') AS name,
                ge.properties_json,
                gr.id AS relation_id,
                gr.source_id,
                gr.target_id,
                gr.relation_type,
                gr.properties_json AS relation_properties_json
            FROM graph_entities ge
            LEFT JOIN graph_relations gr
              ON gr.source_id = ge.id OR gr.target_id = ge.id
            WHERE {where}
            ORDER BY ge.created_at DESC
            LIMIT ?
        """
        params.append(limit)

        try:
            with sqlite3.connect(self.memory_db) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(sql, params).fetchall()
        except Exception:
            return []

        results: List[Dict[str, Any]] = []
        for row in rows:
            rel = None
            if row["relation_id"]:
                rel = {
                    "id": row["relation_id"],
                    "source_id": row["source_id"],
                    "target_id": row["target_id"],
                    "type": row["relation_type"],
                }
            results.append(
                {
                    "entity": {
                        "id": row["entity_id"],
                        "type": row["entity_type"],
                        "name": row["name"],
                        "properties": row["properties_json"],
                    },
                    "relation": rel,
                }
            )
        return results

    def retrieve_experiences(
        self,
        message: str,
        task_understanding: Dict[str, Any],
        recent_days: int = 7,
    ) -> Dict[str, Any]:
        """Track B: retrieve experiences (episodic, semantic, candidate, graph)."""

        task_type = task_understanding.get("task_type", "conversation")
        scenario = task_understanding.get("scenario", "")
        tags = task_understanding.get("tags", [])

        episodic = self.experience_recall.recall(
            task_type=task_type,
            scenario=scenario,
            tags=tags,
            recent_days=recent_days,
        )

        semantic_raw = search_similar(message, top_k=5)
        semantic = []
        for exp, score in semantic_raw:
            semantic.append(
                {
                    "score": round(float(score), 4),
                    "type": exp.get("type"),
                    "timestamp": exp.get("timestamp"),
                    "content": exp.get("content")
                    or exp.get("message")
                    or exp.get("title")
                    or exp.get("summary"),
                    "source": exp.get("source"),
                }
            )

        candidates = self.candidate_memory.get_candidates()
        candidate_matches = [
            c for c in candidates if self._match_candidate(c, task_type, scenario, tags)
        ][:5]

        memories = self._search_memories_fts(message, task_understanding, limit=5)

        graph_matches = self._search_graph_sqlite(task_understanding, limit=5)
        if not graph_matches:
            graph_context = {"task_type": task_type, "scenario": scenario}
            graph_matches = self.graph_memory.search_by_context(graph_context)[:5]

        return {
            "episodic": episodic,
            "semantic": semantic,
            "memories": memories,
            "candidate": candidate_matches,
            "graph": graph_matches,
        }

    def retrieve(
        self, message: str, task_understanding: Dict[str, Any], recent_days: int = 7
    ) -> Dict[str, Any]:
        """Unified retrieve + update hit/miss statistics."""

        rules_track = self.retrieve_rules(task_understanding)
        experience_track = self.retrieve_experiences(
            message=message,
            task_understanding=task_understanding,
            recent_days=recent_days,
        )

        hits = {
            "rules": bool(rules_track.get("rules", {}).get("P0_HARD")),
            "episodic": bool(
                experience_track.get("episodic", {}).get("similar_tasks", [])
            ),
            "semantic": bool(experience_track.get("semantic")),
            "memories": bool(experience_track.get("memories")),
            "candidate": bool(experience_track.get("candidate")),
            "graph": bool(experience_track.get("graph")),
        }

        for track, is_hit in hits.items():
            self._update_track_stat(track, is_hit)

        self.stats["total_calls"] += 1
        self._persist_stats()

        context_summary = self.experience_recall.get_context_summary(
            experience_track.get("episodic", {})
        )
        if experience_track.get("semantic"):
            context_summary += f"\n\n🧠 语义命中: {len(experience_track['semantic'])}条"
        if experience_track.get("memories"):
            context_summary += f"\n🗂️ 记忆命中: {len(experience_track['memories'])}条"
        if experience_track.get("candidate"):
            context_summary += f"\n🧪 候选命中: {len(experience_track['candidate'])}条"
        if experience_track.get("graph"):
            context_summary += f"\n🕸️ 图谱命中: {len(experience_track['graph'])}条"

        recall_priority_order = ["rules", "experience", "candidate"]
        recall_packet = {
            "rules": rules_track,
            "experience": {
                "episodic": experience_track.get("episodic", {}),
                "semantic": experience_track.get("semantic", []),
                "memories": experience_track.get("memories", []),
                "graph": experience_track.get("graph", []),
            },
            "candidate": {
                "candidate": experience_track.get("candidate", []),
            },
        }

        return {
            "timestamp": datetime.now().isoformat(),
            "rules_track": rules_track,
            "experience_track": experience_track,
            "recall_priority_order": recall_priority_order,
            "recall_packet": recall_packet,
            "context_summary": context_summary.strip(),
            "hits": hits,
            "retrieval_stats": self.stats,
        }


_memory_retrieval = None


def get_memory_retrieval() -> MemoryRetrieval:
    global _memory_retrieval
    if _memory_retrieval is None:
        _memory_retrieval = MemoryRetrieval()
    return _memory_retrieval
