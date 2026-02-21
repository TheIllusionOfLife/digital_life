"""Shared helpers for analysis scripts."""

from __future__ import annotations

import json
from pathlib import Path


def load(path: Path) -> list[dict]:
    """Load a JSON array from disk."""
    with open(path) as f:
        return json.load(f)

