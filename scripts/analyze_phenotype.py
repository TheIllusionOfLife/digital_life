"""Phenotype clustering and niche analysis.

Analyzes evolution experiment data to identify emergent phenotypic clusters
and spatial niche associations among populations at the final timestep.

Usage:
    uv run python scripts/analyze_phenotype.py > experiments/phenotype_analysis.json

Output: JSON analysis to stdout + progress to stderr.

Implementation lives in ``analyses/phenotype/``; this file is a thin dispatcher.
"""

from __future__ import annotations

from analyses.phenotype import (
    analyze_long_horizon_sensitivity,  # noqa: F401  (re-export for back-compat)
    main,
)
from analyses.phenotype.clustering import (  # noqa: F401  (re-export for back-compat)
    persistence_claim_gate,
)

if __name__ == "__main__":
    main()
