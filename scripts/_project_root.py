"""Project root resolution via pyproject.toml sentinel.

Import PROJECT_ROOT from here instead of hardcoding parent-hop counts,
so the path survives directory restructuring (e.g. forking into sub-repos).
"""

from __future__ import annotations

from pathlib import Path


def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    # Fallback: _project_root.py lives in scripts/, so two hops up reaches the repo root.
    return here.parents[1]


PROJECT_ROOT: Path = _find_project_root()
