# Digital Life

Digital Life is an artificial life research codebase for building and evaluating computational organisms against seven biological criteria (cellular organization, metabolism, homeostasis, growth/development, reproduction, response to stimuli, and evolution).

The repository is a Rust workspace with optional Python bindings.

## Quick Start

### Prerequisites

- Rust stable toolchain
- `uv` for Python environment and packaging tasks
- `tectonic` for LaTeX paper compilation

### Build

```bash
cargo build --workspace
```

### Test and Lint

```bash
./scripts/check.sh
```

### Python Script Lint/Test

```bash
uv run ruff check scripts tests_python
uv run pytest tests_python
uv run python scripts/check_manuscript_consistency.py
```

### Long-Horizon Niche + Zenodo Metadata

```bash
uv run python scripts/experiment_niche.py --long-horizon
uv run python scripts/analyze_phenotype.py > experiments/phenotype_analysis.json
gzip -c experiments/niche_normal_long.json > experiments/niche_normal_long.json.gz
uv run python scripts/prepare_zenodo_metadata.py experiments/niche_normal_long.json.gz \
  --experiment-name niche_long_horizon \
  --steps 10000 \
  --seed-start 100 \
  --seed-end 129 \
  --paper-binding fig:persistent_clusters=experiments/phenotype_analysis.json \
  --zenodo-doi 10.5281/zenodo.18710600 \
  --output docs/research/zenodo_niche_long_horizon_metadata.json
```

### Artifact Publication Policy (Zenodo)

- Commit code, manifests, compact summaries, and figure-ready outputs.
- Do not commit large raw experiment outputs to git.
- Publish heavy artifacts to Zenodo with checksums and commit provenance.
- Detailed policy: `docs/research/artifact_publication_policy.md`

### Run the Feasibility Spike

```bash
cargo run -p digital-life-spike --release
```

### Build Python Extension (local)

```bash
uv run maturin develop --manifest-path crates/digital-life-py/Cargo.toml
```

Then in Python:

```python
import digital_life
print(digital_life.version())
```

## Repository Docs

- `AGENTS.md`: instructions for coding agents and contributors
- `PRODUCT.md`: product goals and user value
- `TECH.md`: technology stack and technical constraints
- `STRUCTURE.md`: code/documentation layout and conventions
- `docs/README.md`: documentation index
- `docs/research/`: research planning artifacts and historical design docs
- `docs/research/result_manifest_bindings.json`: manifest-to-paper result provenance map

## Architecture (High-Level)

- `crates/digital-life-core`: simulation core (world, metabolism, genome, NN, spatial systems)
- `crates/digital-life-py`: PyO3 bindings exposing core functions to Python
- `crates/spike`: executable benchmark/feasibility experiment runner
- `python/digital_life`: Python package surface for the extension module

## Development Workflow

- Create feature branches from `main`
- Keep commits focused and test-backed
- Open PRs against `main` with test evidence (`fmt`, `clippy`, `test`)

## Current Status

This is an active research prototype. APIs and model details may evolve quickly as experiments progress.
