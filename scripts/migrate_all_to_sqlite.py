#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha1
from pathlib import Path
from typing import Any, Iterator

# Ensure local imports work when this script is executed directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evoclaw.sqlite_memory import SQLiteMemoryStore


def stable_id(prefix: str, payload: Any) -> str:
    digest = sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"{prefix}-{digest}"


def iter_jsonl_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.jsonl"))


def load_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as exc:
                print(f"[WARN] {path}:{lineno} invalid json: {exc}", file=sys.stderr)
                continue
            if not isinstance(obj, dict):
                print(f"[WARN] {path}:{lineno} expected object", file=sys.stderr)
                continue
            yield obj


def load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[WARN] {path} invalid json: {exc}", file=sys.stderr)
        return None
    if not isinstance(obj, dict):
        print(f"[WARN] {path} expected object", file=sys.stderr)
        return None
    return obj


def migrate_experiences(store: SQLiteMemoryStore, memory_root: Path) -> dict[str, int]:
    imported = 0
    skipped = 0
    for dirname in ("experiences", "semantic", "significant"):
        for file_path in iter_jsonl_files(memory_root / dirname):
            for lineno, obj in enumerate(load_jsonl(file_path), start=1):
                if not obj.get("id"):
                    obj["id"] = stable_id(
                        "experience",
                        {"file": str(file_path.relative_to(memory_root)), "lineno": lineno, "obj": obj},
                    )
                if not obj.get("source"):
                    obj["source"] = dirname
                if not obj.get("type"):
                    obj["type"] = dirname
                try:
                    store.upsert_experience(obj)
                    imported += 1
                except Exception as exc:
                    skipped += 1
                    print(
                        f"[WARN] failed to import experience id={obj.get('id')!r}: {exc}",
                        file=sys.stderr,
                    )
    return {"imported": imported, "skipped": skipped}


def migrate_proposals(store: SQLiteMemoryStore, memory_root: Path) -> dict[str, int]:
    proposals_dir = memory_root / "proposals"
    imported = 0
    skipped = 0
    for file_path in iter_jsonl_files(proposals_dir):
        default_status = file_path.stem
        for lineno, obj in enumerate(load_jsonl(file_path), start=1):
            if not obj.get("id"):
                obj["id"] = stable_id(
                    "proposal",
                    {"file": str(file_path.relative_to(memory_root)), "lineno": lineno, "obj": obj},
                )
            metadata = obj.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
                obj["metadata"] = metadata

            if not obj.get("status") and not metadata.get("status"):
                metadata["status"] = default_status
            if (
                (obj.get("status") or metadata.get("status")) == "approved"
                and not obj.get("approved_at")
                and not metadata.get("approved_at")
            ):
                metadata["approved_at"] = obj.get("updated_at") or obj.get("created_at") or ""

            try:
                store.upsert_proposal(obj)
                imported += 1
            except Exception as exc:
                skipped += 1
                print(
                    f"[WARN] failed to import proposal id={obj.get('id')!r}: {exc}",
                    file=sys.stderr,
                )
    return {"imported": imported, "skipped": skipped}


def migrate_reflections(store: SQLiteMemoryStore, memory_root: Path) -> dict[str, int]:
    reflections_dir = memory_root / "reflections"
    imported = 0
    skipped = 0
    if not reflections_dir.exists():
        return {"imported": 0, "skipped": 0}

    for file_path in sorted(reflections_dir.glob("*.json")):
        obj = load_json_file(file_path)
        if obj is None:
            skipped += 1
            continue
        if not obj.get("id"):
            obj["id"] = file_path.stem
        if "analysis" not in obj and "insights" in obj:
            obj["analysis"] = {"insights": obj.get("insights")}
        if "proposals" not in obj:
            obj["proposals"] = []
        try:
            store.upsert_reflection(obj)
            imported += 1
        except Exception as exc:
            skipped += 1
            print(
                f"[WARN] failed to import reflection file={file_path.name!r}: {exc}",
                file=sys.stderr,
            )
    return {"imported": imported, "skipped": skipped}


def migrate_graph(store: SQLiteMemoryStore, memory_root: Path) -> dict[str, int]:
    graph_dir = memory_root / "graph"
    entities_imported = 0
    relations_imported = 0
    skipped = 0

    for lineno, obj in enumerate(load_jsonl(graph_dir / "entities.jsonl"), start=1):
        if not obj.get("id"):
            obj["id"] = stable_id(
                "entity",
                {"file": "graph/entities.jsonl", "lineno": lineno, "obj": obj},
            )
        try:
            store.upsert_entity(obj)
            entities_imported += 1
        except Exception as exc:
            skipped += 1
            print(
                f"[WARN] failed to import entity id={obj.get('id')!r}: {exc}",
                file=sys.stderr,
            )

    for lineno, obj in enumerate(load_jsonl(graph_dir / "relations.jsonl"), start=1):
        if not obj.get("id"):
            obj["id"] = stable_id(
                "relation",
                {"file": "graph/relations.jsonl", "lineno": lineno, "obj": obj},
            )
        try:
            store.upsert_relation(obj)
            relations_imported += 1
        except Exception as exc:
            skipped += 1
            print(
                f"[WARN] failed to import relation id={obj.get('id')!r}: {exc}",
                file=sys.stderr,
            )

    return {
        "entities_imported": entities_imported,
        "relations_imported": relations_imported,
        "skipped": skipped,
    }


def migrate_soul_changes(store: SQLiteMemoryStore, memory_root: Path) -> dict[str, int]:
    imported = 0
    skipped = 0
    for lineno, obj in enumerate(load_jsonl(memory_root / "soul_changes.jsonl"), start=1):
        if not obj.get("id"):
            obj["id"] = stable_id(
                "soul-change",
                {"file": "soul_changes.jsonl", "lineno": lineno, "obj": obj},
            )
        try:
            store.upsert_soul_change(obj)
            imported += 1
        except Exception as exc:
            skipped += 1
            print(
                f"[WARN] failed to import soul change id={obj.get('id')!r}: {exc}",
                file=sys.stderr,
            )
    return {"imported": imported, "skipped": skipped}




def migrate_candidates(store: SQLiteMemoryStore, memory_root: Path) -> dict[str, int]:
    perf_file = memory_root / "skill_performance" / "performance.jsonl"
    imported = 0
    skipped = 0
    if not perf_file.exists():
        return {"imported": 0, "skipped": 0}

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for obj in load_jsonl(perf_file):
        skill_id = str(obj.get("skill_id") or "")
        task_type = str(obj.get("task_type") or "")
        if not skill_id:
            skipped += 1
            continue
        key = (skill_id, task_type)
        grouped.setdefault(key, []).append(obj)

    for (skill_id, task_type), rows in grouped.items():
        total = len(rows)
        success_count = sum(1 for r in rows if bool(r.get("success")))
        score = success_count / total if total else 0.0
        latest_ts = max(str(r.get("timestamp") or r.get("created_at") or "") for r in rows)
        candidate = {
            "id": stable_id("candidate", {"skill_id": skill_id, "task_type": task_type}),
            "skill_id": skill_id,
            "task_type": task_type,
            "status": "candidate",
            "source": "skill_performance",
            "score": score,
            "created_at": latest_ts,
            "updated_at": latest_ts,
            "metadata": {
                "samples": total,
                "success_count": success_count,
                "failure_count": total - success_count,
            },
        }
        try:
            store.upsert_candidate(candidate)
            imported += 1
        except Exception as exc:
            skipped += 1
            print(
                f"[WARN] failed to import candidate skill={skill_id!r} task={task_type!r}: {exc}",
                file=sys.stderr,
            )

    return {"imported": imported, "skipped": skipped}

def read_json_or_jsonl(path: Path) -> Any:
    if path.suffix == ".json":
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    if path.suffix == ".jsonl":
        return list(load_jsonl(path))
    return None


def migrate_state(store: SQLiteMemoryStore, memory_root: Path) -> dict[str, int]:
    imported = 0
    skipped = 0

    evoclaw_state = read_json_or_jsonl(memory_root / "evoclaw-state.json")
    if evoclaw_state is not None:
        store.upsert_state("evoclaw-state", evoclaw_state, "")
        imported += 1

    for dirname in ("tasks", "working", "feedback"):
        base = memory_root / dirname
        if not base.exists():
            continue
        for file_path in sorted(base.glob("*.json*")):
            payload = read_json_or_jsonl(file_path)
            if payload is None:
                skipped += 1
                continue
            key = f"{dirname}/{file_path.name}"
            store.upsert_state(key, payload, "")
            imported += 1

    return {"imported": imported, "skipped": skipped}


def run(memory_root: Path, db_path: Path) -> int:
    store = SQLiteMemoryStore(db_path)
    store.init_schema()

    summary = {
        "experiences": migrate_experiences(store, memory_root),
        "proposals": migrate_proposals(store, memory_root),
        "reflections": migrate_reflections(store, memory_root),
        "graph": migrate_graph(store, memory_root),
        "soul_changes": migrate_soul_changes(store, memory_root),
        "candidates": migrate_candidates(store, memory_root),
        "state": migrate_state(store, memory_root),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Migration finished: db={db_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate all memory data into SQLite memory.db"
    )
    parser.add_argument(
        "--memory-root",
        default="memory",
        help="Path to memory root (default: ./memory)",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to sqlite db (default: <memory-root>/memory.db)",
    )
    args = parser.parse_args()

    memory_root = Path(args.memory_root).resolve()
    db_path = (
        Path(args.db_path).resolve()
        if args.db_path
        else (memory_root / "memory.db").resolve()
    )
    return run(memory_root, db_path)


if __name__ == "__main__":
    raise SystemExit(main())
