# AGENTS.md

This file provides repository-specific instructions for coding agents and contributors.

## Mission

Build and evolve the Digital Life simulation with reproducible, testable changes aligned with the seven-criteria research goals.

## High-Confidence Commands

- Build workspace: `cargo build --workspace`
- Run full checks: `./scripts/check.sh`
- Run spike benchmark: `cargo run -p digital-life-spike --release`
- Build Python extension: `uv run maturin develop --manifest-path crates/digital-life-py/Cargo.toml`
- Compile paper: `cd paper && tectonic main.tex`

## Code Style and Quality Rules

- Rust style is default `rustfmt` output with `clippy` warnings treated as errors.
- Keep modules cohesive and domain-driven (`world`, `metabolism`, `organism`, `nn`, `spatial`).
- Add/keep tests close to changed logic (`#[cfg(test)] mod tests`).
- Prefer minimal, direct fixes over broad refactors unless required.

## Testing Instructions

- Baseline gate for all changes: `./scripts/check.sh`
- For Python-binding changes, always run Rust tests in `crates/digital-life-py/src/lib.rs` through the full test command.

## Repository Etiquette

- Branch naming: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`, `refactor/<topic>`, `test/<topic>`
- Never push directly to `main`.
- Keep commits small, logically grouped, and prefixed (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`).
- PRs should include the problem, solution, and exact verification commands run.

## Architecture Decisions to Preserve

- Rust core simulation with Python bindings via PyO3/maturin.
- Two metabolism modes are currently supported (`toy`, `graph`).
- Criterion-ablation toggles are config-driven and should stay easy to test.
- Simulation behavior should remain reproducible via deterministic seeds.

## Environment and Tooling Quirks

- Use `uv` for Python-related tooling; avoid ad-hoc global package installs.
- Use `tectonic` for LaTeX compilation (not `latexmk` or `pdflatex`). Run `cd paper && tectonic main.tex` to produce the PDF.
- Running `cargo run -p digital-life-spike` without `--release` yields non-representative performance.
- Local build artifacts (`target/`, extension binaries) should remain untracked.

## Non-Obvious Gotchas

- `num_organisms * agents_per_organism` is bounded; exceeding limits is rejected by runtime checks.
- JSON config compatibility matters: legacy config payloads should still deserialize with defaults when possible.
- Research planning docs are in `docs/research/`; do not treat them as implementation truth over code/tests.
