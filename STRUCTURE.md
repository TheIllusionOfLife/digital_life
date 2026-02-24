# STRUCTURE.md

## Top-Level Layout

- `Cargo.toml`: Rust workspace manifest
- `crates/`: Rust crates
- `configs/`: Versioned experiment configuration JSON files (see `configs/README.md`)
- `python/`: Python package source
- `scripts/`: Experiment runners, analysis scripts, figure generators
- `.github/workflows/`: CI and automation workflows
- `docs/`: project and research documentation

## Crates

- `crates/digital-life-core/src/`
  - `constants.rs`: shared compile-time constants (MAX_WORLD_SIZE, RNG_DERIVATION_PRIME, GENOME_DIVERSITY_MAX_PAIRS)
  - `world/mod.rs`: World struct, `step()` orchestrator, experiment harnesses, reproduction helpers
  - `world/phases/`: six simulation phase modules (nn_query, agent_state, boundary, metabolism, growth, environment)
  - `world/tests.rs`: determinism, long-run stability, and regression tests for World
  - `metrics.rs`: step metric types and `collect_step_metrics()` — single source of truth for all metric structs
  - `metabolism.rs`: metabolism logic
  - `organism.rs`, `agent.rs`, `resource.rs`: organism-level model types
  - `nn.rs`: neural controller
  - `spatial.rs`: spatial indexing and neighborhood operations
  - `config.rs`: simulation configuration model and validation
- `crates/digital-life-py/src/lib.rs`: Python binding entry points
- `crates/spike/src/main.rs`: benchmark and feasibility executable

## Python Surface

- `python/digital_life/__init__.py`: public Python API exports

## Scripts Layout

- `scripts/experiment_common.py`: shared config helpers and experiment runners; loads `TUNED_BASELINE` from `configs/tuned_baseline.json`; preferred entry point is `run_condition_suite()` (handles seed loop, JSON output, and TSV header); lower-level `run_single()` and `run_condition_common()` remain for custom experiments
- `scripts/experiment_*.py`: per-experiment drivers (thin wrappers around `experiment_common`)
- `scripts/analyze_*.py`: analysis scripts (statistics, coupling, phenotype)
- `scripts/generate_figures.py`: figure dispatcher — calls per-figure functions
- `scripts/figures/`: per-figure-family modules (split from the monolith)
- `scripts/analyses/`: analysis subpackage (statistics, coupling, phenotype modules)
- `scripts/experiment_utils.py`: **deprecated** — import from `experiment_common` directly
- `scripts/analysis_utils.py`: **deprecated** — inline or use `analyses/` package

## Configs Layout

See `configs/README.md` for provenance of each file.

- `configs/tuned_baseline.json`: calibrated baseline parameters (loaded by `experiment_common.py`)

## Naming and Module Conventions

- Rust: `snake_case` for functions/modules, `CamelCase` for types
- Keep tests colocated in `#[cfg(test)] mod tests` near implementation
- Keep docs and research notes under `docs/` instead of root-level sprawl

## Documentation Organization

- Root docs (`README.md`, `AGENTS.md`, `PRODUCT.md`, `TECH.md`, `STRUCTURE.md`) are canonical operational docs
- `docs/research/` stores planning/review artifacts; `action-plan.md` is authoritative
- `docs/research/unified-review.md` and `docs/research/functional-analogy-definition.md` are historical reference — do not delete
- Zenodo artifact policy for heavy outputs: `docs/research/artifact_publication_policy.md`
- Repository should keep heavy experiment artifacts out of git; track compact summaries + provenance manifests instead

## Experiment Execution Order

Run scripts in this order; each stage depends on outputs from the prior stage.

| Stage | Script | Key output files |
|-------|--------|-----------------|
| 1. Core ablation | `experiment_final_graph.py` | `experiments/final_graph_{condition}.json` |
| 1. Core ablation | `experiment_final.py` | `experiments/final_{condition}.json` |
| 1. Evolution | `experiment_evolution.py` | `experiments/evolution_{variant}.json` |
| 1. Cyclic | `experiment_cyclic.py` | `experiments/cyclic_{condition}.json` |
| 1. Niche | `experiment_niche.py` | `experiments/niche_{condition}.json` |
| 2. Analysis | `analyze_results.py` | `experiments/final_graph_statistics.json`, `experiments/final_statistics.json` |
| 2. Analysis | `analyze_coupling.py` | `experiments/coupling_analysis.json` |
| 2. Analysis | `analyze_phenotype.py` | `experiments/phenotype_analysis.json` |
| 2. Analysis | `analyze_evolution_evidence.py` | `experiments/evolution_evidence.json` |
| 3. Figures | `generate_figures.py` | `paper/figures/fig_*.pdf` |

Most analysis scripts require `experiments/final_graph_normal.json` (produced by
`experiment_final_graph.py`) as their primary input. Run Stage 1 first in a fresh clone.
