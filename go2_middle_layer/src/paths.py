"""
Path constants resolved relative to the source directory.

Use these when paths must work regardless of the current working directory
(e.g. when running `python src/server.py` from project root).
"""

from pathlib import Path

# Directory containing server.py, mcps, resources, etc.
SRC_DIR = Path(__file__).resolve().parent
# Project root (parent of src/)
PROJECT_ROOT = SRC_DIR.parent


def resolve_src_path(relative_path: str) -> Path:
    """Resolve a path relative to src/ to an absolute Path."""
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return (SRC_DIR / path).resolve()


def resolve_project_path(relative_path: str) -> Path:
    """Resolve a path relative to project root to an absolute Path."""
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()
