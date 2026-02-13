# Criterion-Ablation Experiment: Final Analysis

**Experiment**: 2000 steps, n=30 per condition (seeds 100-129), Holm-Bonferroni corrected
**Date**: 2026-02-13
**Commit**: 55b8952 (includes energy loss bug fix)

## Results Summary

| Criterion | Normal | Ablated | Delta % | Cohen's d | p_corrected | Significant |
|-----------|--------|---------|---------|-----------|-------------|-------------|
| Metabolism | 322.0 | 46.0 | -85.7% | 15.3 | <0.001 | yes |
| Reproduction | 322.0 | 31.6 | -90.2% | 16.0 | <0.001 | yes |
| Response | 322.0 | 39.6 | -87.7% | 15.5 | <0.001 | yes |
| Boundary | 322.0 | 64.8 | -79.9% | 6.7 | <0.001 | yes |
| Homeostasis | 322.0 | 69.6 | -78.4% | 4.5 | <0.001 | yes |
| Growth | 322.0 | 193.8 | -39.8% | 5.3 | <0.001 | yes |
| Evolution | 322.0 | 298.4 | -7.3% | 0.8 | 0.003 | yes |

**7/7 criteria significant** after Holm-Bonferroni correction (alpha = 0.05).

## Go/No-Go Assessment

### Verdict: GO -- Tier 2 (Full Paper) is achievable

### Against Action Plan Tiers

**Tier 1 (Extended Abstract)** -- all checks pass:
- 3+ criteria functional: 7/7
- Autonomous maintenance >1000 steps: yes (2000 steps, mean ~322 alive)
- Calibration/test separation: yes (seeds 0-99 calibration, 100-129 test)

**Tier 2 (Full Paper)** -- status:
- 7 criteria functioning simultaneously: yes
- Criterion-ablation shows degradation: 7/7 significant
- Final test set with Holm-Bonferroni: yes, all pass
- Population-level evolution with adaptation: weak but significant (d=0.8)
- Literature comparison with rubric: not yet done (writing phase task)

## Key Findings

1. **Five criteria are indispensable** -- removing metabolism, reproduction, response,
   boundary, or homeostasis causes >78% population collapse with massive effect sizes
   (d > 4).

2. **Growth is functionally necessary** -- 40% degradation with d=5.3. Immature organisms
   cannot reproduce and have reduced metabolic efficiency, creating real developmental
   pressure.

3. **Evolution is the weakest signal** -- only 7.3% degradation (d=0.8, small-to-medium
   effect). Statistically significant but the weakest criterion by far. Evolution operates
   over generations and 2000 steps may not be enough for the full effect to emerge. For
   the paper, this can be framed as "evolution provides optimization rather than survival
   necessity at short timescales."

4. **Functional analogy conditions are met** -- each criterion satisfies:
   - (a) Dynamic process requiring sustained resource consumption
   - (b) Removal causes measurable degradation of organism self-maintenance
   - (c) Forms feedback loops with at least one other criterion
     (e.g., homeostasis -> boundary repair -> survival -> metabolism)

## Remaining Work for Paper

The simulation and experiment infrastructure is complete. Remaining tasks are primarily
in the writing phase:

- Paper skeleton -> full draft (Methods, Results, Discussion)
- Literature comparison table (Polyworld, ALIEN, Flow-Lenia, Avida, Lenia, Coralai)
- Figures (population dynamics curves, ablation bar chart)
- Careful framing of the evolution result
