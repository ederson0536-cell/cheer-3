#!/usr/bin/env python3
"""Unified workspace path resolver."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_workspace(current_file: str | os.PathLike | None = None) -> Path:
    """Resolve workspace root using env override first, then file location."""
    env = os.getenv("OPENCLAW_WORKSPACE") or os.getenv("WORKSPACE_CHEER_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    if current_file:
        path = Path(current_file).resolve()
        # file under <workspace>/evoclaw/** or <workspace>/scripts/**
        if "evoclaw" in path.parts:
            idx = path.parts.index("evoclaw")
            return Path(*path.parts[:idx]).resolve()
        if "scripts" in path.parts:
            idx = path.parts.index("scripts")
            return Path(*path.parts[:idx]).resolve()

    return Path.cwd().resolve()
