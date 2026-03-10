#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for


def create_app(memory_dir: Path | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = "evoclaw-memory-ui"

    root = Path(__file__).resolve().parents[2]
    memory_root = (memory_dir or root / "memory").resolve()
    app.config["MEMORY_ROOT"] = memory_root
    focus_dirs = {"experiences", "significant", "semantic", "candidate", "rules", "proposals"}
    default_page_size = 50

    def resolve_safe_path(relative_path: str) -> Path:
        candidate = (memory_root / relative_path).resolve()
        if memory_root == candidate or memory_root in candidate.parents:
            if candidate.is_file():
                return candidate
        raise FileNotFoundError("Invalid file path")

    def parse_jsonl(raw_text: str) -> tuple[list[str], list[dict], str | None]:
        rows: list[dict] = []
        columns: list[str] = []
        error = None
        for line_no, line in enumerate(raw_text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                error = f"Line {line_no}: {exc.msg}"
                break
            if not isinstance(obj, dict):
                obj = {"value": obj}
            rows.append(obj)
            for key in obj.keys():
                if key not in columns:
                    columns.append(key)
        return columns, rows, error

    def parse_int(value: str | None, default: int, *, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value or "")
        except ValueError:
            return default
        return max(minimum, min(maximum, parsed))

    def sort_records(
        records: list[dict], sort_key: str, order: str, fallback: Callable[[dict], object]
    ) -> list[dict]:
        reverse = order == "desc"
        def normalize(value: object) -> object:
            if isinstance(value, (int, float)):
                return value
            if value is None:
                return ""
            return str(value).lower()
        return sorted(
            records,
            key=lambda item: (
                item.get(sort_key) is None,
                normalize(item.get(sort_key) if sort_key in item else fallback(item)),
            ),
            reverse=reverse,
        )

    def paginate(items: list[dict], page: int, page_size: int) -> tuple[list[dict], int, int]:
        total = len(items)
        total_pages = max(1, math.ceil(total / page_size)) if total else 1
        page = max(1, min(page, total_pages))
        start = (page - 1) * page_size
        end = start + page_size
        return items[start:end], page, total_pages

    @app.route("/")
    def index():
        files = []
        directories = set()
        query = request.args.get("q", "").strip().lower()
        sort = request.args.get("sort", "modified")
        order = request.args.get("order", "desc").lower()
        page = parse_int(request.args.get("page"), 1, minimum=1, maximum=100000)
        page_size = parse_int(
            request.args.get("page_size"), default_page_size, minimum=1, maximum=500
        )
        valid_sorts = {"path", "directory", "size", "modified"}
        if sort not in valid_sorts:
            sort = "modified"
        if order not in {"asc", "desc"}:
            order = "desc"

        if memory_root.exists():
            for path in sorted(p for p in memory_root.rglob("*") if p.is_file()):
                rel = path.relative_to(memory_root).as_posix()
                directory = str(Path(rel).parent)
                directories.add("" if directory == "." else directory)
                stat = path.stat()
                files.append(
                    {
                        "path": rel,
                        "directory": directory,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "modified_ts": stat.st_mtime,
                        "focused": rel.split("/", 1)[0] in focus_dirs,
                    }
                )
        if query:
            files = [
                item
                for item in files
                if query in item["path"].lower() or query in item["directory"].lower()
            ]
        files = sort_records(
            files,
            "modified_ts" if sort == "modified" else sort,
            order,
            fallback=lambda item: item["path"],
        )
        total_count = len(files)
        files, page, total_pages = paginate(files, page, page_size)
        directory_list = sorted(d for d in directories if d)
        return render_template(
            "index.html",
            files=files,
            directories=directory_list,
            focus_dirs=sorted(focus_dirs),
            q=query,
            sort=sort,
            order=order,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_count=total_count,
        )

    @app.route("/file/<path:relative_path>")
    def view_file(relative_path: str):
        try:
            file_path = resolve_safe_path(relative_path)
        except FileNotFoundError:
            flash("文件不存在或路径非法", "error")
            return redirect(url_for("index"))

        content = file_path.read_text(encoding="utf-8")
        columns: list[str] = []
        rows: list[dict] = []
        parse_error = None
        row_query = request.args.get("q", "").strip().lower()
        row_sort = request.args.get("sort", "")
        row_order = request.args.get("order", "desc").lower()
        row_page = parse_int(request.args.get("page"), 1, minimum=1, maximum=100000)
        row_page_size = parse_int(
            request.args.get("page_size"), default_page_size, minimum=1, maximum=500
        )
        row_total_count = 0
        row_total_pages = 1

        if file_path.suffix == ".jsonl":
            columns, rows, parse_error = parse_jsonl(content)
            if row_query:
                rows = [
                    row
                    for row in rows
                    if row_query in json.dumps(row, ensure_ascii=False, sort_keys=True).lower()
                ]
            if rows:
                selected_sort = row_sort if row_sort in columns else (columns[0] if columns else "")
                if selected_sort:
                    rows = sort_records(
                        rows,
                        selected_sort,
                        row_order if row_order in {"asc", "desc"} else "desc",
                        fallback=lambda row: "",
                    )
                row_sort = selected_sort
            row_total_count = len(rows)
            rows, row_page, row_total_pages = paginate(rows, row_page, row_page_size)

        return render_template(
            "view_file.html",
            relative_path=relative_path,
            content=content,
            columns=columns,
            rows=rows,
            parse_error=parse_error,
            is_json=file_path.suffix in {".json", ".jsonl"},
            q=row_query,
            sort=row_sort,
            order=row_order,
            page=row_page,
            page_size=row_page_size,
            total_pages=row_total_pages,
            total_count=row_total_count,
        )

    @app.route("/save/<path:relative_path>", methods=["POST"])
    def save_file(relative_path: str):
        try:
            file_path = resolve_safe_path(relative_path)
        except FileNotFoundError:
            flash("文件不存在或路径非法", "error")
            return redirect(url_for("index"))

        content = request.form.get("content", "")

        try:
            if file_path.suffix == ".json":
                json.loads(content)
            elif file_path.suffix == ".jsonl":
                for line_no, line in enumerate(content.splitlines(), start=1):
                    if line.strip():
                        json.loads(line)
        except json.JSONDecodeError as exc:
            flash(f"JSON 语法错误: line {exc.lineno}, col {exc.colno} - {exc.msg}", "error")
            return redirect(url_for("view_file", relative_path=relative_path))

        file_path.write_text(content, encoding="utf-8")
        flash("保存成功", "success")
        return redirect(url_for("view_file", relative_path=relative_path))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
