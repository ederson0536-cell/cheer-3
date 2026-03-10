"""Path resolution utilities with security checks."""

from pathlib import Path


def resolve_safe_path(
    user_path: str,
    *,
    root: Path | None = None,
    must_exist: bool = False,
    label: str = "path",
) -> Path:
    """Resolve user path within root and reject traversal outside it.
    
    Args:
        user_path: The path provided by the user
        root: The root directory to constrain the path within
        must_exist: Whether the path must exist
        label: Label for error messages
        
    Returns:
        Resolved Path object
        
    Raises:
        SystemExit: If path is invalid or outside root
    """
    if not user_path or not user_path.strip():
        raise SystemExit(f"Invalid {label}: empty path")

    safe_root = (root or Path.cwd()).resolve()
    candidate = Path(user_path).expanduser()
    if not candidate.is_absolute():
        candidate = safe_root / candidate

    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise SystemExit(f"Invalid {label}: {exc}") from exc

    try:
        resolved.relative_to(safe_root)
    except ValueError:
        raise SystemExit(
            f"Invalid {label}: must stay within workspace root '{safe_root}'"
        )

    if must_exist and not resolved.exists():
        raise SystemExit(f"Invalid {label}: file not found '{resolved}'")

    return resolved
