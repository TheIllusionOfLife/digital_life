# Paper Skeleton — Digital Life: ALIFE 2026 Full Paper (8p)

## Working Title

**Digital Life: A Computational System Satisfying Seven Biological Criteria Through Functional Analogy**

## Contribution Statement

We present the first artificial life system that integrates all seven textbook biological criteria for life — cellular organization, metabolism, homeostasis, growth/development, reproduction, response to stimuli, and evolution — as interdependent, dynamic computational processes. Through a criterion-ablation experiment, we demonstrate that each criterion is functionally necessary: its removal causes measurable degradation of organism self-maintenance. Our hybrid swarm-organism architecture achieves this integration while maintaining computational tractability on commodity hardware.

## Section Outline

### 1. Abstract (~150 words)
- Problem: Existing ALife systems implement life criteria as independent modules or simplified proxies
- Approach: Functional analogy framework + hybrid two-layer architecture
- Method: Criterion-ablation experiment (7 individual ablations + baseline)
- Result: Each criterion's removal causes statistically significant system degradation
- Significance: First system demonstrating functional interdependence of all 7 criteria

### 2. Introduction (~1.5 pages)
- The question of computational life and its criteria
- **Functional Analogy** operational definition (3 conditions: dynamic process, measurable degradation, feedback loop)
- Distinction from "simplified proxy" approaches
- Weak ALife stance: functional model, not claim of life itself
- Contributions list (3 items)

### 3. Related Work (~1 page)
- Overview of existing ALife systems (Polyworld, ALIEN, Flow-Lenia, Avida, Lenia, Coralai)
- **Systems comparison table**: 7-criteria coverage matrix with 5-level rubric
- Gap analysis: no existing system integrates all 7 as interdependent processes
- Connection to autopoiesis theory

### 4. System Design (~2 pages)
- Hybrid two-layer architecture (swarm agents → organism-level structures)
- 7 criteria implementation mapping (table: biological criterion → computational process)
- Genotype-phenotype mapping (variable-length genome, 7 segments)
- Neural controller architecture (8→16→4, evolutionary)
- Environment model (continuous 2D, toroidal, resource field)

### 5. Criterion-Ablation Experiment (~1.5 pages)
- Experimental protocol: each criterion individually disabled
- Data separation: calibration set (seeds 0-99) vs. final test set (seeds 100-199)
- Statistical design: Mann-Whitney U, Holm-Bonferroni correction, Cohen's d
- Metrics: alive count, energy, boundary integrity, reproduction rate, genome drift

### 6. Results (~1 page)
- Baseline performance (normal condition)
- Ablation results table (7 conditions vs. metrics)
- Statistical significance of each ablation
- Time-series comparison (normal vs. ablated)

### 7. Discussion (~0.5 page)
- Interpretation: which criteria show strongest interdependence
- Limitations: growth toggle placeholder, computational scale, Weak ALife framing
- Connection to functional analogy definition
- Epistemological scope

### 8. Conclusion (~0.25 page)
- Summary of contributions
- Future work: open-ended evolution, LLM ablation study, scaling

### References

## Figure Plan (minimum 4)

| # | Type | Content | Section |
|---|------|---------|---------|
| 1 | Architecture diagram | Hybrid two-layer: environment → organisms → swarm agents, with 7 criteria annotated | System Design |
| 2 | Table | Criterion-ablation results: 8 conditions × key metrics, with statistical significance markers | Results |
| 3 | Time-series plot | Alive count over 1000 steps for normal vs. each ablation condition (8 lines) | Results |
| 4 | Comparison table | 7 systems × 7 criteria rubric scores (5-level) | Related Work |
| 5 | Diagram (stretch) | Feedback loop map showing interdependencies between criteria | Discussion |

## Target Success Tier

**Tier 2** (Full Paper): All 7 criteria integrated with criterion-ablation proof of functional necessity and interdependence. Statistical validation on held-out test set with multiple comparison correction.

## Key Deadlines

- Week 4 milestone: Methods + Experimental Setup sections substantially complete (3-4 pages)
- Week 7: Full evaluation + figures complete
- Week 7.5-8: Final paper (8p) submitted by 2026-04-01
