"""Proxy control comparison experiment.

Runs 3 metabolism conditions on the same seeds to demonstrate that
graph metabolism provides qualitative advantage over simpler proxies.

Conditions:
  1. graph   - Full graph-based multi-step metabolism
  2. toy     - Intermediate single-step with waste dynamics
  3. counter - Minimal single-step, no waste production

Usage:
    uv run python scripts/experiment_proxy.py > experiments/proxy_data.tsv

Output: TSV data to stdout + summary report to stderr.
"""

import digital_life
from experiment_common import log, run_condition_suite

STEPS = 2000
SAMPLE_EVERY = 50
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

CONDITIONS = {
    "graph": {"metabolism_mode": "graph"},
    "toy": {"metabolism_mode": "toy"},
    "counter": {"metabolism_mode": "counter"},
}


def main():
    """Run proxy control comparison experiment across 3 metabolism modes."""
    log(f"Digital Life v{digital_life.version()}")
    log(
        f"Proxy control experiment: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})"
    )
    log("")
    run_condition_suite("proxy_", CONDITIONS, STEPS, SEEDS, SAMPLE_EVERY)


if __name__ == "__main__":
    main()
