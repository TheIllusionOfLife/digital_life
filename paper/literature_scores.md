# Literature Comparison Scores

Scoring rubric (1--5):
1. No feature
2. Static parameter (e.g., fixed energy value)
3. Dynamic single process (e.g., energy consumption only)
4. Multi-process interaction (e.g., metabolic pathway branching)
5. Self-maintaining/emergent (e.g., autonomous metabolic regulation)

---

## Polyworld (Yaeger 1994)

- Cell.Org: 2 --- Agents are fixed-geometry trapezoids with genetically encoded size; the boundary is a static graphical shape, not an actively maintained structure.
- Metab: 3 --- Agents consume food or prey to replenish a single energy scalar that depletes through movement, fighting, and neural activity; this is a dynamic single-resource process without multi-step transformation.
- Homeo: 1 --- No internal-state regulation mechanism; energy depletes monotonically until replenished by eating. There is no set-point or feedback controller for internal variables.
- Growth: 1 --- Agents are born at full size determined by genome; there is no ontogenetic growth or developmental program.
- Reprod: 3 --- Sexual reproduction with crossover and mutation when two agents express the mate behavior; offspring genome is constructed dynamically, but the process is a single triggered event rather than a multi-stage developmental sequence.
- Response: 4 --- Vision-based perception (rendered scene from agent's viewpoint) feeds a genetically specified neural network that controls 7 behaviors (move, turn, eat, mate, fight, focus, light); Hebbian learning allows lifetime adaptation, making this a multi-process sensorimotor loop.
- Evol: 4 --- Haploid sexual reproduction with crossover, mutation, and natural selection across genetically encoded physiology and neural architecture; small-world network topologies and speciation emerge, but there is no recombination of higher-level modules or sympatric speciation mechanism, keeping it short of level 5.

## Avida (Ofria & Wilke 2004)

- Cell.Org: 2 --- Each organism occupies a single discrete cell on a lattice; the "boundary" is a fixed grid position, not an actively maintained structure.
- Metab: 3 --- Organisms earn SIPs (single-instruction processing units, analogous to ATP) by performing Boolean logic computations on environmental inputs; energy is consumed per instruction executed. This is a dynamic process but involves a single currency (SIPs) without multi-step metabolic pathways.
- Homeo: 1 --- No internal-state regulation; organisms have a stored energy level that decreases with instruction execution and increases with task completion, but there is no set-point control or feedback regulation.
- Growth: 2 --- Genome length can change across generations via insertion/deletion mutations, but there is no within-lifetime developmental program; each organism executes its fixed circular genome from birth.
- Reprod: 4 --- Self-replication is the core mechanism: organisms copy their own genome instruction-by-instruction into a new memory space and then divide. The copy process is integrated with the organism's computational metabolism (using the same CPU cycles), creating interaction between reproduction and metabolic activity.
- Response: 3 --- Organisms can sense environmental states (e.g., nutrient gradients, limited resources) and some evolve phenotypic plasticity (static or dynamic), altering execution based on inputs. However, sensing is limited to reading binary inputs; there is no spatial perception or complex behavioral repertoire.
- Evol: 5 --- Avida is the gold standard for digital evolution: heritable circular genomes undergo point mutation, insertion, deletion, and (optionally) recombination; fitness is emergent from metabolic rate and replication speed; major evolutionary transitions, neutral networks, and epistasis have been demonstrated. Genuinely open-ended and self-sustaining.

## Lenia (Chan 2019)

- Cell.Org: 3 --- Spatially localized patterns (SLPs) maintain coherent boundaries through continuous convolution dynamics; patterns exhibit self-repair and resilience to perturbation, but the boundary emerges from a single update rule rather than from active multi-process maintenance.
- Metab: 1 --- No explicit energy or resource system in base Lenia; state values are updated purely by the CA rule without any notion of consumption or transformation of resources.
- Homeo: 2 --- Patterns maintain stable configurations (attractors) in state space, but this is a consequence of the fixed CA rule parameters rather than an active regulatory process; it is closer to a static equilibrium than dynamic homeostasis.
- Growth: 2 --- In multi-channel extensions (Lenia v3+, 2020), some patterns exhibit growth by ingestion and morphogenesis, but in the original 2019 system, patterns emerge at a characteristic size determined by kernel parameters without a developmental trajectory.
- Reprod: 2 --- Self-replication was discovered in multi-kernel/multi-channel extensions (Chan 2020), not the original system. When present, it occurs as pattern splitting under specific parameter regimes; it is not a robust, general mechanism but rather a narrow phenomenon.
- Response: 3 --- Creatures exhibit chemotaxis-like behavior, collision avoidance, and directed locomotion in response to other patterns, constituting a dynamic single-process response. However, there is no explicit sensory mechanism; responses emerge from the local CA update rule.
- Evol: 2 --- Pattern discovery uses external genetic algorithms or interactive evolutionary computation; there is no intrinsic evolution within the simulation. The CA rule does not natively support heritable variation and selection among competing patterns.

## ALIEN (Heinemann 2008)

- Cell.Org: 4 --- Organisms are networks of typed particles (nerve, sensor, muscle, constructor, attacker) connected by bonds; structures can be partially damaged, fuse, or fall apart. The multi-component architecture with specialized cell types constitutes multi-process boundary maintenance, though boundaries are not fully self-repairing autonomously.
- Metab: 3 --- Cells possess internal energy that depletes through radiation and action execution; energy is absorbed from free energy particles. This is a dynamic single-currency energy flow (emission/absorption) without multi-step metabolic transformation pathways.
- Homeo: 2 --- Cells decay when energy falls below a critical threshold, and energy conservation is maintained across the system; however, there is no active regulatory mechanism that maintains internal state around a set point. The threshold acts as a static parameter.
- Growth: 3 --- Constructor cells can build new cells and extend structures according to encoded blueprints; organisms grow by adding cells dynamically during their lifetime. This is a dynamic constructive process, but growth follows a predetermined blueprint rather than emerging from multi-process developmental interaction.
- Reprod: 4 --- Self-inspecting replication: constructor cells read a genome (blueprint) and build a copy of the parent organism cell-by-cell. The process interacts with the energy system (construction costs energy) and the structural system (new cells must be correctly bonded), constituting multi-process interaction.
- Response: 4 --- Sensor cells detect nearby clusters at specific distances and directions; nerve cells process information via neural networks; muscle cells produce movement. This is a multi-component sensorimotor pipeline (sense -> process -> actuate) with differentiated cell types.
- Evol: 4 --- Random mutations act on genomes during self-replication; natural selection emerges from competition for energy and space. Open-ended evolution is a design goal and has been partially demonstrated. However, evidence for sustained complexification and major evolutionary transitions remains limited compared to Avida.

## Flow-Lenia (Plantec et al. 2023)

- Cell.Org: 3 --- SLPs maintain coherent boundaries through mass-conservative dynamics with localized parameter vectors that flow with the matter; each creature carries its own rule set, enabling individuation. However, boundary maintenance is still governed by a single CA update mechanism rather than multiple interacting processes.
- Metab: 3 --- Mass decays continuously and must be replenished by consuming environmental food (red-channel digestion); this creates a dynamic resource-acquisition loop. However, there is only a single resource type and a single transformation step (food -> mass), not a multi-step metabolic network.
- Homeo: 3 --- Creatures exhibit adaptive behavioral responses to mass depletion (e.g., developing mouth-like structures, switching from static to mobile behavior when resources are scarce). This is a dynamic self-regulatory process, though it emerges from the CA rule rather than from an explicit multi-variable regulatory system.
- Growth: 3 --- Creatures grow by accumulating mass from food; division occurs when sufficient mass is reached. This is a dynamic mass-accumulation process, but there is no staged developmental program or morphological differentiation during growth.
- Reprod: 3 --- Division and fusion emerge spontaneously: creatures split when they accumulate sufficient mass and can merge upon collision. This is a dynamic emergent process, but it is a single mechanism (mass-threshold splitting) without multi-process coordination between genome copying, energy budgeting, and structural assembly.
- Response: 3 --- Creatures exhibit chemotaxis, angular motion, directed locomotion, and obstacle navigation. These are dynamic behavioral responses to local gradients, but arise from a single CA update mechanism without differentiated sensory/motor subsystems.
- Evol: 3 --- Localized parameter vectors flow with mass and undergo random mutations (introduced via targeted beams); different species with different update rules coexist and compete. This is a dynamic evolutionary process with heritable variation and selection, but the mutation mechanism is externally imposed (beams) rather than intrinsic to reproduction, and evidence for sustained open-ended evolution is preliminary.

## Coralai (Barbieux 2024)

- Cell.Org: 3 --- Organisms are spatially coherent NCA patterns on a multi-channel grid (infrastructure, energy, communication channels); they maintain spatial identity through local neural update rules. Boundary maintenance is dynamic but relies on a single NCA mechanism.
- Metab: 3 --- Energy is added/removed via a day/night cycle; organisms transform energy into infrastructure via Invest/Liquidate actuators. This involves a dynamic transformation between two resource types (energy and infrastructure), approaching but not quite reaching multi-pathway metabolism.
- Homeo: 2 --- Organisms adapt to environmental energy cycles, but there is no explicit internal-state regulation with set points or feedback controllers; resilience to perturbation is an emergent property of the NCA update rule rather than an active homeostatic mechanism.
- Growth: 3 --- Organisms can grow spatially on the grid by extending their NCA patterns and investing energy into infrastructure. This is a dynamic growth process, but there is no staged developmental program or differentiation.
- Reprod: 3 --- Reproduction occurs through local merging and mutation operations implemented with HyperNEAT; organisms can split or bud. This is a dynamic process but lacks the multi-stage coordination of genome copying, energy partitioning, and structural assembly seen in higher-scoring systems.
- Response: 3 --- Organisms exhibit competition, resource exploitation, and niche differentiation (sessile vs. mobile strategies), indicating environmental responsiveness. Communication channels enable inter-organism signaling. However, there are no differentiated sensor/actuator subsystems.
- Evol: 3 --- Local survival selection, merging, and mutation via HyperNEAT enable intrinsic evolution with heritable neural network parameters. Multiple species and symbiotic relationships emerge. However, the system is recent and evidence for sustained open-ended evolution or major transitions is limited.

---

## Summary Table

| System | Cell.Org | Metab | Homeo | Growth | Reprod | Response | Evol | Total |
|--------|----------|-------|-------|--------|--------|----------|------|-------|
| Polyworld (1994) | 2 | 3 | 1 | 1 | 3 | 4 | 4 | 18 |
| Avida (2004) | 2 | 3 | 1 | 2 | 4 | 3 | 5 | 20 |
| Lenia (2019) | 3 | 1 | 2 | 2 | 2 | 3 | 2 | 15 |
| ALIEN (2008) | 4 | 3 | 2 | 3 | 4 | 4 | 4 | 24 |
| Flow-Lenia (2023) | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 21 |
| Coralai (2024) | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 20 |

---

## Scoring Notes

**Conservative scoring rationale**: Scores reflect what is documented in primary publications and official documentation. When a feature exists only in later extensions (e.g., Lenia self-replication in 2020 multi-channel version), the score reflects the base system as published, with a note about extensions. When evidence for a capability is anecdotal or preliminary, the score is kept at the lower bound.

**Key observations**:
- No existing system scores above 3 on Homeostasis, reflecting a general gap in the field.
- Evolution is the strongest criterion across classical systems (Avida, Polyworld), while newer CA-based systems (Lenia, Flow-Lenia) are weaker here due to reliance on external search.
- ALIEN achieves the highest total by combining multi-component structure with constructive reproduction, but lacks multi-step metabolism and active homeostasis.
- Flow-Lenia is notable for achieving uniform level-3 scores across all criteria, reflecting its balanced but shallow coverage.

**Sources**:
- Yaeger, L. (1994). Computational genetics, physiology, metabolism, neural systems, learning, vision, and behavior or PolyWorld: Life in a new context. *Santa Fe Institute Studies in the Sciences of Complexity*, 17, 263--263.
- Ofria, C. & Wilke, C.O. (2004). Avida: A software platform for research in computational evolutionary biology. *Artificial Life*, 10(2), 191--229.
- Chan, B.W.-C. (2019). Lenia -- Biology of Artificial Life. *Complex Systems*, 28(3), 251--286.
- Heinemann, C. (~2021). ALIEN: Artificial Life Environment. https://alien-project.org
- Plantec, E. et al. (2023). Flow-Lenia: Towards open-ended evolution in cellular automata through mass conservation and parameter localization. *Proc. ALIFE 2023*.
- Barbieux, A. (2024). Coralai: Intrinsic evolution of embodied neural cellular automata ecosystems. *Proc. ALIFE 2024*.
