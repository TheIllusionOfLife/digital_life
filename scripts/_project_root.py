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
    # Fallback: two hops from scripts/ (original assumption)
    return here.parent


PROJECT_ROOT: Path = _find_project_root()
