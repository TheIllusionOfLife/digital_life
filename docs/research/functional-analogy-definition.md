# Functional Analogy: Operational Definition

> **Document Role:** Formal definition of "Functional Analogy" as used in this project, distinguishing it from simplified proxy approaches. This definition is the theoretical backbone of the criterion-ablation experiment.

## Definition

A computational process is a **functional analogy** of a biological criterion if and only if it satisfies all three conditions:

**(a) Dynamic Process** — The process requires sustained resource consumption to operate. It is not a static property or fixed parameter, but an ongoing computation that consumes energy, time, or other resources at each timestep.

**(b) Measurable Degradation** — Removal (ablation) of the process causes measurable degradation of the organism's self-maintenance capacity. This is verified empirically via the criterion-ablation experiment: disabling the process leads to statistically significant reduction in organism viability metrics (alive count, energy, boundary integrity).

**(c) Feedback Loop** — The process forms a feedback loop with at least one other criterion. Changes in this process affect another criterion's behavior, and vice versa. This interdependence means the criteria cannot be understood as independent modules.

## Distinction from Simplified Proxy

A **simplified proxy** is a computational element that nominally corresponds to a biological criterion but fails conditions (b) and/or (c):

- Removing a proxy does not degrade the system (it is decorative, not functional)
- A proxy operates independently of other criteria (no feedback loop)

| Property | Functional Analogy | Simplified Proxy |
|----------|-------------------|-----------------|
| Resource consumption | Continuous, per-step | None or one-time |
| Effect of removal | System degradation | No measurable impact |
| Interdependence | Feedback with other criteria | Independent module |
| Verification | Criterion-ablation experiment | Cannot be falsified |

## Mapping: 7 Biological Criteria → Functional Analogy Conditions

### 1. Cellular Organization (Boundary Maintenance)

| Condition | How satisfied |
|-----------|--------------|
| (a) Dynamic | Swarm agents actively maintain boundary; boundary decays without energy investment per step |
| (b) Degradation | `enable_boundary_maintenance=false` → boundary integrity drops to zero → organism death |
| (c) Feedback | Boundary integrity ↔ Metabolism (energy funds repair; boundary collapse kills organism, stopping metabolism) |

### 2. Metabolism

| Condition | How satisfied |
|-----------|--------------|
| (a) Dynamic | Graph-based metabolic network transforms external resources into energy each step; waste accumulates |
| (b) Degradation | `enable_metabolism=false` → no energy production → boundary repair fails → death |
| (c) Feedback | Metabolism ↔ Boundary (energy enables repair); Metabolism ↔ Homeostasis (energy level is regulated state) |

### 3. Homeostasis

| Condition | How satisfied |
|-----------|--------------|
| (a) Dynamic | NN controller regulates internal state vector (internal_state[0], internal_state[1]) each step |
| (b) Degradation | `enable_homeostasis=false` → internal state frozen → no adaptive regulation → reduced viability |
| (c) Feedback | Homeostasis ↔ Metabolism (regulates energy usage); Homeostasis ↔ Response (internal state informs behavioral output) |

### 4. Growth/Development

| Condition | How satisfied |
|-----------|--------------|
| (a) Dynamic | Developmental program transforms minimal seed into mature organism (agent recruitment, metabolic network expansion) |
| (b) Degradation | `enable_growth=false` → organisms cannot develop beyond seed state → reduced fitness |
| (c) Feedback | Growth ↔ Metabolism (growth consumes energy); Growth ↔ Reproduction (maturity required for reproduction) |

**Note:** Growth/development toggle is currently a placeholder. The developmental program will be implemented in Week 5. The mapping above describes the intended design.

### 5. Reproduction

| Condition | How satisfied |
|-----------|--------------|
| (a) Dynamic | Organism-initiated division when metabolically ready; parent pays energy cost; offspring develops from seed |
| (b) Degradation | `enable_reproduction=false` → population cannot grow → eventual extinction from aging/damage |
| (c) Feedback | Reproduction ↔ Metabolism (requires energy threshold); Reproduction ↔ Evolution (offspring carry mutated genomes) |

### 6. Response to Stimuli

| Condition | How satisfied |
|-----------|--------------|
| (a) Dynamic | NN processes local sensory field (position, velocity, neighbors, internal state) → velocity delta each step |
| (b) Degradation | `enable_response=false` → agents do not adjust velocity from NN → no adaptive movement → reduced resource acquisition |
| (c) Feedback | Response ↔ Metabolism (movement enables resource gathering); Response ↔ Homeostasis (internal state informs NN input) |

### 7. Evolution

| Condition | How satisfied |
|-----------|--------------|
| (a) Dynamic | Heritable genomes undergo mutation during reproduction; differential survival across generations |
| (b) Degradation | `enable_evolution=false` → no genetic variation → population cannot adapt to environmental change |
| (c) Feedback | Evolution ↔ Reproduction (mutation occurs during reproduction); Evolution ↔ all criteria (genome encodes parameters for all criteria) |

## Verification Protocol

At each Go/No-Go checkpoint, verify:

> "For each implemented criterion at this stage, can we explain in one paragraph why it is a functional analogy and not a simplified proxy?"

This requires demonstrating:
1. The process consumes resources per step (not a static lookup)
2. Ablation produces measurable degradation (cite specific metric delta)
3. At least one feedback loop with another criterion is observable (cite specific interaction)

## Connection to Existing Frameworks

| Framework | Relationship to Functional Analogy |
|-----------|-----------------------------------|
| NASA definition ("self-sustaining chemical system capable of Darwinian evolution") | Our definition is more fine-grained: we require 7 independently verifiable criteria, not 2 bundled conditions |
| Autopoiesis (Maturana & Varela) | Active boundary + metabolism = computational autopoiesis; our framework extends this to 5 additional criteria |
| Ruiz-Mirazo et al. minimal conditions | Compatible but more specific: we operationalize each condition with ablation-testable implementations |
| Textbook 7 criteria (Campbell Biology) | Direct adoption, enhanced with functional analogy conditions (a)-(c) to prevent proxy implementations |
