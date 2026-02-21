# STRUCTURE.md

## Top-Level Layout

- `Cargo.toml`: Rust workspace manifest
- `crates/`: Rust crates
- `python/`: Python package source
- `.github/workflows/`: CI and automation workflows
- `docs/`: project and research documentation

## Crates

- `crates/digital-life-core/src/`
  - `world.rs`: simulation world/state transitions
  - `metabolism.rs`: metabolism logic
  - `organism.rs`, `agent.rs`, `resource.rs`: organism-level model types
  - `nn.rs`: neural controller
  - `spatial.rs`: spatial indexing and neighborhood operations
  - `config.rs`: simulation configuration model
- `crates/digital-life-py/src/lib.rs`: Python binding entry points
- `crates/spike/src/main.rs`: benchmark and feasibility executable

## Python Surface

- `python/digital_life/__init__.py`: public Python API exports

## Naming and Module Conventions

- Rust: `snake_case` for functions/modules, `CamelCase` for types
- Keep tests colocated in `#[cfg(test)] mod tests` near implementation
- Keep docs and research notes under `docs/` instead of root-level sprawl

## Documentation Organization

- Root docs (`README.md`, `AGENTS.md`, `PRODUCT.md`, `TECH.md`, `STRUCTURE.md`) are canonical operational docs
- `docs/research/` stores planning/review artifacts that inform but do not replace code-level source of truth
- Zenodo artifact policy for heavy outputs: `docs/research/artifact_publication_policy.md`
- Repository should keep heavy experiment artifacts out of git; track compact summaries + provenance manifests instead
