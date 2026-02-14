use std::collections::HashMap;
use std::sync::OnceLock;

/// Per-organism metabolic state.
#[derive(Clone, Debug)]
pub struct MetabolicState {
    pub energy: f32,
    pub resource: f32,
    pub waste: f32,
    // Per-organism carry-over pool for graph intermediates between simulation steps.
    pub graph_pool: Vec<f32>,
}

impl Default for MetabolicState {
    fn default() -> Self {
        Self {
            energy: 0.5,
            resource: 5.0,
            waste: 0.0,
            graph_pool: Vec::new(),
        }
    }
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct MetabolismFlux {
    pub consumed_external: f32,
    pub consumed_total: f32,
    pub produced_waste: f32,
}

/// Future-facing node definition for genetically encoded graph metabolism.
#[derive(Clone, Debug)]
pub struct MetabolicNode {
    pub id: u16,
    pub catalytic_efficiency: f32,
}

/// Future-facing edge definition for graph metabolism.
#[derive(Clone, Debug)]
pub struct MetabolicEdge {
    pub from: u16,
    pub to: u16,
    pub flux_ratio: f32,
}

/// Graph topology scaffold used by the graph metabolism strategy.
#[derive(Clone, Debug)]
pub struct MetabolicGraph {
    pub nodes: Vec<MetabolicNode>,
    pub edges: Vec<MetabolicEdge>,
}

impl MetabolicGraph {
    pub fn bootstrap_single_path() -> Self {
        Self {
            nodes: vec![MetabolicNode {
                id: 0,
                catalytic_efficiency: 1.0,
            }],
            edges: Vec::new(),
        }
    }
}

#[derive(Clone, Debug)]
pub struct ToyMetabolism {
    pub uptake_rate: f32,
    pub conversion_efficiency: f32,
    pub waste_ratio: f32,
    pub energy_loss_rate: f32,
    pub max_energy: f32,
    pub waste_decay_rate: f32,
    pub max_waste: f32,
}

impl Default for ToyMetabolism {
    fn default() -> Self {
        Self {
            uptake_rate: 0.4,
            conversion_efficiency: 0.8,
            waste_ratio: 0.2,
            energy_loss_rate: 0.02,
            max_energy: 1.0,
            waste_decay_rate: 0.05,
            max_waste: 1.0,
        }
    }
}

impl ToyMetabolism {
    pub fn step(
        &self,
        state: &mut MetabolicState,
        external_resource: f32,
        dt: f32,
    ) -> MetabolismFlux {
        let params = MetabolismParams::from_toy(self);
        apply_metabolism_step(
            params,
            self.conversion_efficiency,
            state,
            external_resource,
            dt,
        )
    }
}

const DEFAULT_EDGE_TRANSFER_EFFICIENCY: f32 = 0.98;

// Genome decoding constants
const MIN_NODE_COUNT: f32 = 2.0;
const MAX_NODE_COUNT: f32 = 4.0;
const NODE_COUNT_SCALE: f32 = 2.0;
const NODE_COUNT_OFFSET: f32 = 2.0;
const CATALYTIC_EFF_SCALE: f32 = 0.9;
const CATALYTIC_EFF_OFFSET: f32 = 0.1;
const EDGE_EXISTENCE_THRESHOLD: f32 = 0.3;
const FLUX_RATIO_MIN: f32 = 0.1;
const FLUX_RATIO_MAX: f32 = 1.0;
const EDGE_TRANSFER_EFF_SCALE: f32 = 0.3;
const EDGE_TRANSFER_EFF_OFFSET: f32 = 0.7;
const CONVERSION_EFF_SCALE: f32 = 0.7;
const CONVERSION_EFF_OFFSET: f32 = 0.3;

fn sigmoid(x: f32) -> f32 {
    1.0 / (1.0 + (-x).exp())
}

/// Decode a 16-float genome segment into entry node ID for a graph with `node_count` nodes.
///
/// # Panics
///
/// Panics if `segment.len() < 2`.
pub fn decode_entry_node_id(segment: &[f32], node_count: usize) -> u16 {
    assert!(segment.len() >= 2, "segment must have at least 2 elements");
    let raw = (sigmoid(segment[1]) * node_count as f32).floor() as usize;
    raw.min(node_count.saturating_sub(1)) as u16
}

/// Decode a 16-float genome segment into a `MetabolicGraph`.
///
/// Encoding scheme (16 floats):
/// - [0]: node count → clamp(round(sigmoid(x)*2+2), 2, 4)
/// - [1]: entry node → floor(sigmoid(x)*node_count)
/// - [2-5]: catalytic efficiency per node → sigmoid(x)*0.9+0.1 → [0.1, 1.0]
/// - [6-11]: edge weights for pairs (0,1)(0,2)(0,3)(1,2)(1,3)(2,3)
///   abs(x)>0.3 → edge exists; sign → direction; clamp(abs(x),0.1,1.0) → flux_ratio
/// - [12]: edge transfer efficiency → sigmoid(x)*0.3+0.7 → [0.7, 1.0]
/// - [13]: conversion efficiency → sigmoid(x)*0.7+0.3 → [0.3, 1.0]
/// - 14-15: reserved
pub fn decode_metabolic_graph(segment: &[f32]) -> MetabolicGraph {
    assert!(
        segment.len() >= 16,
        "segment must have at least 16 elements"
    );

    let node_count = (sigmoid(segment[0]) * NODE_COUNT_SCALE + NODE_COUNT_OFFSET)
        .round()
        .clamp(MIN_NODE_COUNT, MAX_NODE_COUNT) as usize;

    let nodes: Vec<MetabolicNode> = (0..node_count)
        .map(|i| {
            let eff = sigmoid(segment[2 + i]) * CATALYTIC_EFF_SCALE + CATALYTIC_EFF_OFFSET;
            MetabolicNode {
                id: i as u16,
                catalytic_efficiency: eff,
            }
        })
        .collect();

    // Edge pairs for up to 4 nodes: (0,1)(0,2)(0,3)(1,2)(1,3)(2,3) at slots 6..12
    let edge_pairs: [(usize, usize); 6] = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)];
    let mut edges = Vec::new();
    for (slot, &(i, j)) in edge_pairs.iter().enumerate() {
        if i >= node_count || j >= node_count {
            continue;
        }
        let val = segment[6 + slot];
        if val.abs() <= EDGE_EXISTENCE_THRESHOLD {
            continue;
        }
        let (from, to) = if val > 0.0 { (i, j) } else { (j, i) };
        let flux_ratio = val.abs().clamp(FLUX_RATIO_MIN, FLUX_RATIO_MAX);
        edges.push(MetabolicEdge {
            from: from as u16,
            to: to as u16,
            flux_ratio,
        });
    }

    MetabolicGraph { nodes, edges }
}

/// Decode a 16-float genome segment into a full `GraphMetabolism` engine.
pub fn decode_graph_metabolism(segment: &[f32]) -> GraphMetabolism {
    let graph = decode_metabolic_graph(segment);
    let entry_node_id = decode_entry_node_id(segment, graph.nodes.len());
    let edge_transfer_efficiency =
        sigmoid(segment[12]) * EDGE_TRANSFER_EFF_SCALE + EDGE_TRANSFER_EFF_OFFSET;
    let conversion_efficiency = sigmoid(segment[13]) * CONVERSION_EFF_SCALE + CONVERSION_EFF_OFFSET;

    assert!(
        validate_metabolic_graph(&graph, entry_node_id),
        "decoded graph must be structurally valid"
    );

    GraphMetabolism {
        graph,
        entry_node_id,
        edge_transfer_efficiency,
        conversion_efficiency,
        ..GraphMetabolism::default()
    }
}

/// Validate a decoded metabolic graph for structural correctness.
pub fn validate_metabolic_graph(graph: &MetabolicGraph, entry_node_id: u16) -> bool {
    if graph.nodes.is_empty() {
        return false;
    }
    if !graph.nodes.iter().any(|n| n.id == entry_node_id) {
        return false;
    }
    let node_ids: std::collections::HashSet<u16> = graph.nodes.iter().map(|n| n.id).collect();
    for node in &graph.nodes {
        if !node.catalytic_efficiency.is_finite() {
            return false;
        }
    }
    for edge in &graph.edges {
        if !node_ids.contains(&edge.from) || !node_ids.contains(&edge.to) {
            return false;
        }
        if !(0.0..=1.0).contains(&edge.flux_ratio) {
            return false;
        }
    }
    true
}

#[derive(Debug)]
pub struct GraphMetabolism {
    pub graph: MetabolicGraph,
    pub entry_node_id: u16,
    pub uptake_rate: f32,
    pub conversion_efficiency: f32,
    pub waste_ratio: f32,
    pub energy_loss_rate: f32,
    pub max_energy: f32,
    pub waste_decay_rate: f32,
    pub max_waste: f32,
    pub edge_transfer_efficiency: f32,
    node_index_cache: OnceLock<HashMap<u16, usize>>,
}

impl Default for GraphMetabolism {
    fn default() -> Self {
        let toy = ToyMetabolism::default();
        Self {
            graph: MetabolicGraph::bootstrap_single_path(),
            entry_node_id: 0,
            uptake_rate: toy.uptake_rate,
            conversion_efficiency: toy.conversion_efficiency,
            waste_ratio: toy.waste_ratio,
            energy_loss_rate: toy.energy_loss_rate,
            max_energy: toy.max_energy,
            waste_decay_rate: toy.waste_decay_rate,
            max_waste: toy.max_waste,
            edge_transfer_efficiency: DEFAULT_EDGE_TRANSFER_EFFICIENCY,
            node_index_cache: OnceLock::new(),
        }
    }
}

impl GraphMetabolism {
    fn node_index_by_id(&self) -> &HashMap<u16, usize> {
        self.node_index_cache.get_or_init(|| {
            self.graph
                .nodes
                .iter()
                .enumerate()
                .map(|(idx, node)| (node.id, idx))
                .collect()
        })
    }
}

impl Clone for GraphMetabolism {
    fn clone(&self) -> Self {
        Self {
            graph: self.graph.clone(),
            entry_node_id: self.entry_node_id,
            uptake_rate: self.uptake_rate,
            conversion_efficiency: self.conversion_efficiency,
            waste_ratio: self.waste_ratio,
            energy_loss_rate: self.energy_loss_rate,
            max_energy: self.max_energy,
            waste_decay_rate: self.waste_decay_rate,
            max_waste: self.max_waste,
            edge_transfer_efficiency: self.edge_transfer_efficiency,
            node_index_cache: OnceLock::new(),
        }
    }
}

impl GraphMetabolism {
    pub fn step(
        &self,
        state: &mut MetabolicState,
        external_resource: f32,
        dt: f32,
    ) -> MetabolismFlux {
        if self.graph.nodes.is_empty() {
            let params = MetabolismParams::from_graph(self);
            return apply_metabolism_step(
                params,
                self.conversion_efficiency.clamp(0.0, 1.0),
                state,
                external_resource,
                dt,
            );
        }

        let external_cap = (self.uptake_rate * dt).max(0.0);
        let consumed_external = external_resource.max(0.0).min(external_cap);
        state.resource += consumed_external;

        let uptake = (self.uptake_rate * dt).min(state.resource).max(0.0);
        state.resource -= uptake;

        let node_count = self.graph.nodes.len();
        if state.graph_pool.len() != node_count {
            state.graph_pool = vec![0.0; node_count];
        }
        let node_index_by_id = self.node_index_by_id();
        let entry_idx = node_index_by_id
            .get(&self.entry_node_id)
            .copied()
            .unwrap_or(0);
        state.graph_pool[entry_idx] += uptake;
        let current = std::mem::take(&mut state.graph_pool);
        let mut next = vec![0.0f32; node_count];

        let mut terminal_product = 0.0f32;
        let mut inefficiency_loss = 0.0f32;

        for (idx, node) in self.graph.nodes.iter().enumerate() {
            let substrate = current[idx].max(0.0);
            if substrate <= 0.0 {
                continue;
            }

            let produced = substrate * node.catalytic_efficiency.clamp(0.0, 1.0);
            inefficiency_loss += substrate - produced;

            let mut allocated = 0.0f32;
            for edge in self.graph.edges.iter().filter(|edge| edge.from == node.id) {
                if let Some(&to_idx) = node_index_by_id.get(&edge.to) {
                    if allocated >= produced {
                        break;
                    }
                    let ratio = edge.flux_ratio.clamp(0.0, 1.0);
                    if ratio == 0.0 {
                        continue;
                    }
                    let desired = produced * ratio;
                    let flow = desired.min(produced - allocated);
                    let transferred = flow * self.edge_transfer_efficiency.clamp(0.0, 1.0);
                    next[to_idx] += transferred;
                    allocated += flow;
                    inefficiency_loss += flow - transferred;
                }
            }

            terminal_product += produced - allocated;
        }

        state.graph_pool = next;

        state.energy += terminal_product * self.conversion_efficiency.clamp(0.0, 1.0);
        let produced_waste = inefficiency_loss
            + terminal_product * (1.0 - self.conversion_efficiency.clamp(0.0, 1.0));
        state.waste += produced_waste;
        state.waste = (state.waste - self.waste_decay_rate * dt).clamp(0.0, self.max_waste);

        let retained = (1.0 - self.energy_loss_rate * dt).clamp(0.0, 1.0);
        state.energy = (state.energy * retained).clamp(0.0, self.max_energy);

        MetabolismFlux {
            consumed_external,
            consumed_total: uptake,
            produced_waste,
        }
    }
}

/// Minimal single-step metabolism for proxy control experiments.
///
/// Converts external resource to energy with a flat efficiency.
/// No graph intermediates, no waste dynamics beyond baseline decay.
/// Serves as the simplest possible metabolism satisfying "dynamic + resource-consuming".
#[derive(Clone, Debug)]
pub struct CounterMetabolism {
    pub flat_efficiency: f32,
    pub energy_loss_rate: f32,
    pub max_energy: f32,
    pub waste_decay_rate: f32,
    pub max_waste: f32,
    pub uptake_rate: f32,
}

impl Default for CounterMetabolism {
    fn default() -> Self {
        let toy = ToyMetabolism::default();
        Self {
            flat_efficiency: 0.5,
            energy_loss_rate: toy.energy_loss_rate,
            max_energy: toy.max_energy,
            waste_decay_rate: toy.waste_decay_rate,
            max_waste: toy.max_waste,
            uptake_rate: toy.uptake_rate,
        }
    }
}

impl CounterMetabolism {
    pub fn step(
        &self,
        state: &mut MetabolicState,
        external_resource: f32,
        dt: f32,
    ) -> MetabolismFlux {
        // Single-step: consume external resource, add energy directly
        let external_cap = (self.uptake_rate * dt).max(0.0);
        let consumed_external = external_resource.max(0.0).min(external_cap);
        state.energy += consumed_external * self.flat_efficiency;

        // Same energy loss rate as other modes for fairness
        let retained = (1.0 - self.energy_loss_rate * dt).clamp(0.0, 1.0);
        state.energy = (state.energy * retained).clamp(0.0, self.max_energy);

        // Waste decays but is not produced (no multi-step processing)
        state.waste = (state.waste - self.waste_decay_rate * dt).clamp(0.0, self.max_waste);

        MetabolismFlux {
            consumed_external,
            consumed_total: consumed_external,
            produced_waste: 0.0,
        }
    }
}

#[derive(Clone, Debug)]
pub enum MetabolismEngine {
    Toy(ToyMetabolism),
    Graph(GraphMetabolism),
    Counter(CounterMetabolism),
}

impl Default for MetabolismEngine {
    fn default() -> Self {
        Self::Toy(ToyMetabolism::default())
    }
}

impl MetabolismEngine {
    pub fn step(
        &self,
        state: &mut MetabolicState,
        external_resource: f32,
        dt: f32,
    ) -> MetabolismFlux {
        match self {
            MetabolismEngine::Toy(engine) => engine.step(state, external_resource, dt),
            MetabolismEngine::Graph(engine) => engine.step(state, external_resource, dt),
            MetabolismEngine::Counter(engine) => engine.step(state, external_resource, dt),
        }
    }
}

#[derive(Clone, Copy, Debug)]
struct MetabolismParams {
    uptake_rate: f32,
    waste_ratio: f32,
    energy_loss_rate: f32,
    max_energy: f32,
    waste_decay_rate: f32,
    max_waste: f32,
}

impl MetabolismParams {
    fn from_toy(engine: &ToyMetabolism) -> Self {
        Self {
            uptake_rate: engine.uptake_rate,
            waste_ratio: engine.waste_ratio,
            energy_loss_rate: engine.energy_loss_rate,
            max_energy: engine.max_energy,
            waste_decay_rate: engine.waste_decay_rate,
            max_waste: engine.max_waste,
        }
    }

    fn from_graph(engine: &GraphMetabolism) -> Self {
        Self {
            uptake_rate: engine.uptake_rate,
            waste_ratio: engine.waste_ratio,
            energy_loss_rate: engine.energy_loss_rate,
            max_energy: engine.max_energy,
            waste_decay_rate: engine.waste_decay_rate,
            max_waste: engine.max_waste,
        }
    }
}

fn apply_metabolism_step(
    params: MetabolismParams,
    conversion_efficiency: f32,
    state: &mut MetabolicState,
    external_resource: f32,
    dt: f32,
) -> MetabolismFlux {
    let external_cap = (params.uptake_rate * dt).max(0.0);
    let consumed_external = external_resource.max(0.0).min(external_cap);
    state.resource += consumed_external;

    let uptake = (params.uptake_rate * dt).min(state.resource).max(0.0);
    state.resource -= uptake;
    state.energy += uptake * conversion_efficiency;
    state.waste += uptake * params.waste_ratio;
    state.waste = (state.waste - params.waste_decay_rate * dt).clamp(0.0, params.max_waste);

    // Minimal thermodynamic loss to avoid unbounded free energy growth.
    let retained = (1.0 - params.energy_loss_rate * dt).clamp(0.0, 1.0);
    state.energy = (state.energy * retained).clamp(0.0, params.max_energy);

    MetabolismFlux {
        consumed_external,
        consumed_total: uptake,
        produced_waste: uptake * params.waste_ratio,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn energy_is_bounded() {
        let mut state = MetabolicState::default();
        let metabolism = ToyMetabolism {
            uptake_rate: 10.0,
            conversion_efficiency: 1.0,
            energy_loss_rate: 0.0,
            ..ToyMetabolism::default()
        };
        for _ in 0..100 {
            state.resource += 10.0;
            metabolism.step(&mut state, 0.0, 1.0);
        }
        assert!(
            (0.0..=metabolism.max_energy).contains(&state.energy),
            "energy out of bounds: {}",
            state.energy
        );
    }

    #[test]
    fn waste_is_bounded() {
        let mut state = MetabolicState::default();
        let metabolism = ToyMetabolism {
            uptake_rate: 10.0,
            waste_ratio: 1.0,
            waste_decay_rate: 0.0,
            ..ToyMetabolism::default()
        };
        for _ in 0..100 {
            state.resource += 10.0;
            metabolism.step(&mut state, 0.0, 1.0);
        }
        assert!(
            (0.0..=metabolism.max_waste).contains(&state.waste),
            "waste out of bounds: {}",
            state.waste
        );
    }

    #[test]
    fn external_resource_is_consumed() {
        let mut state = MetabolicState {
            resource: 0.0,
            ..MetabolicState::default()
        };
        let metabolism = ToyMetabolism::default();
        let flux = metabolism.step(&mut state, 1.0, 1.0);
        assert!(flux.consumed_external > 0.0);
        assert!(state.energy > 0.0);
    }

    #[test]
    fn graph_engine_produces_bounded_state() {
        let mut state = MetabolicState::default();
        let metabolism = GraphMetabolism::default();
        for _ in 0..100 {
            let _ = metabolism.step(&mut state, 1.0, 1.0);
        }
        assert!((0.0..=metabolism.max_energy).contains(&state.energy));
        assert!((0.0..=metabolism.max_waste).contains(&state.waste));
    }

    #[test]
    fn graph_topology_changes_energy_outcome() {
        let mut connected_state = MetabolicState::default();
        let mut disconnected_state = MetabolicState::default();

        let connected = GraphMetabolism {
            graph: MetabolicGraph {
                nodes: vec![
                    MetabolicNode {
                        id: 0,
                        catalytic_efficiency: 1.0,
                    },
                    MetabolicNode {
                        id: 1,
                        catalytic_efficiency: 1.0,
                    },
                ],
                edges: vec![MetabolicEdge {
                    from: 0,
                    to: 1,
                    flux_ratio: 1.0,
                }],
            },
            conversion_efficiency: 1.0,
            max_energy: 10.0,
            ..GraphMetabolism::default()
        };

        let disconnected = GraphMetabolism {
            graph: MetabolicGraph {
                nodes: vec![
                    MetabolicNode {
                        id: 0,
                        catalytic_efficiency: 1.0,
                    },
                    MetabolicNode {
                        id: 1,
                        catalytic_efficiency: 1.0,
                    },
                ],
                edges: Vec::new(),
            },
            conversion_efficiency: 1.0,
            max_energy: 10.0,
            ..GraphMetabolism::default()
        };

        for _ in 0..10 {
            let _ = connected.step(&mut connected_state, 1.0, 1.0);
            let _ = disconnected.step(&mut disconnected_state, 1.0, 1.0);
        }

        assert!(
            (connected_state.energy - disconnected_state.energy).abs() > f32::EPSILON,
            "connected and disconnected graphs should produce different energy outcomes"
        );
    }

    #[test]
    fn graph_cycle_retains_mass_in_resource_pool() {
        let mut state = MetabolicState {
            energy: 0.0,
            resource: 0.0,
            waste: 0.0,
            ..MetabolicState::default()
        };
        let metabolism = GraphMetabolism {
            graph: MetabolicGraph {
                nodes: vec![
                    MetabolicNode {
                        id: 0,
                        catalytic_efficiency: 1.0,
                    },
                    MetabolicNode {
                        id: 1,
                        catalytic_efficiency: 1.0,
                    },
                ],
                edges: vec![
                    MetabolicEdge {
                        from: 0,
                        to: 1,
                        flux_ratio: 1.0,
                    },
                    MetabolicEdge {
                        from: 1,
                        to: 0,
                        flux_ratio: 1.0,
                    },
                ],
            },
            conversion_efficiency: 1.0,
            waste_ratio: 0.0,
            energy_loss_rate: 0.0,
            max_energy: 10.0,
            entry_node_id: 0,
            edge_transfer_efficiency: 1.0,
            ..GraphMetabolism::default()
        };
        let _ = metabolism.step(&mut state, 1.0, 1.0);
        assert!(
            state.graph_pool.iter().sum::<f32>() > 0.0,
            "cycle intermediates should be retained, not lost"
        );
    }

    // ── decode_metabolic_graph tests ──

    #[test]
    fn decode_zero_genome_produces_valid_graph() {
        let segment = [0.0f32; 16];
        let graph = decode_metabolic_graph(&segment);
        // sigmoid(0) = 0.5 → node_count = round(0.5*2+2) = 3
        assert_eq!(graph.nodes.len(), 3);
        // No edges: all edge slot values are 0.0, abs(0.0) <= 0.3
        assert!(graph.edges.is_empty());
        // Entry node exists in nodes
        let entry = decode_entry_node_id(&segment, graph.nodes.len());
        assert!(
            graph.nodes.iter().any(|n| n.id == entry),
            "entry node must exist in decoded graph"
        );
    }

    #[test]
    fn decode_nonzero_genome_produces_edges() {
        let mut segment = [0.0f32; 16];
        // Set edge slots (6-11) to values with abs > 0.3
        segment[6] = 0.5;
        segment[7] = -0.8;
        segment[8] = 1.0;
        let graph = decode_metabolic_graph(&segment);
        assert!(
            !graph.edges.is_empty(),
            "segment with values > 0.3 in edge slots should produce edges"
        );
    }

    #[test]
    fn decode_is_deterministic() {
        let segment = [
            0.1, -0.5, 0.3, 0.7, -0.2, 0.9, 0.4, -0.6, 0.8, -0.1, 0.5, -0.3, 0.2, 0.6, 0.0, 0.0,
        ];
        let a = decode_metabolic_graph(&segment);
        let b = decode_metabolic_graph(&segment);
        assert_eq!(a.nodes.len(), b.nodes.len());
        assert_eq!(a.edges.len(), b.edges.len());
        for (na, nb) in a.nodes.iter().zip(&b.nodes) {
            assert_eq!(na.id, nb.id);
            assert_eq!(na.catalytic_efficiency, nb.catalytic_efficiency);
        }
        for (ea, eb) in a.edges.iter().zip(&b.edges) {
            assert_eq!(ea.from, eb.from);
            assert_eq!(ea.to, eb.to);
            assert_eq!(ea.flux_ratio, eb.flux_ratio);
        }
    }

    #[test]
    fn decode_clamps_values() {
        // Extreme values should produce valid clamped ranges
        let segment = [
            100.0, -100.0, 50.0, -50.0, 99.0, -99.0, 10.0, -10.0, 5.0, -5.0, 3.0, -3.0, 100.0,
            -100.0, 0.0, 0.0,
        ];
        let graph = decode_metabolic_graph(&segment);
        assert!((2..=4).contains(&graph.nodes.len()));
        for node in &graph.nodes {
            assert!(
                (0.1..=1.0).contains(&node.catalytic_efficiency),
                "catalytic_efficiency {} out of range",
                node.catalytic_efficiency
            );
        }
        for edge in &graph.edges {
            assert!(
                (0.1..=1.0).contains(&edge.flux_ratio),
                "flux_ratio {} out of range",
                edge.flux_ratio
            );
        }
    }

    #[test]
    fn decode_different_segments_produce_different_graphs() {
        let a = decode_metabolic_graph(&[0.0; 16]);
        let b = decode_metabolic_graph(&[1.0; 16]);
        let same_topology = a.nodes.len() == b.nodes.len() && a.edges.len() == b.edges.len();
        let same_efficiency = a.nodes.iter().zip(&b.nodes).all(|(na, nb)| {
            (na.catalytic_efficiency - nb.catalytic_efficiency).abs() < f32::EPSILON
        });
        assert!(
            !(same_topology && same_efficiency),
            "different segments should produce different graphs"
        );
    }

    // ── decode_graph_metabolism tests ──

    #[test]
    fn decode_graph_metabolism_sets_efficiencies_from_genome() {
        let mut segment = [0.0f32; 16];
        segment[12] = 1.0; // edge_transfer_efficiency → sigmoid(1.0)*0.3+0.7
        segment[13] = -1.0; // conversion_efficiency → sigmoid(-1.0)*0.7+0.3
        let gm = decode_graph_metabolism(&segment);
        // sigmoid(1.0) ≈ 0.731 → 0.731*0.3+0.7 ≈ 0.919
        assert!(gm.edge_transfer_efficiency > 0.7 && gm.edge_transfer_efficiency <= 1.0);
        // sigmoid(-1.0) ≈ 0.269 → 0.269*0.7+0.3 ≈ 0.488
        assert!(gm.conversion_efficiency > 0.3 && gm.conversion_efficiency <= 1.0);
    }

    #[test]
    fn decode_graph_metabolism_zero_produces_functional_engine() {
        let segment = [0.0f32; 16];
        let gm = decode_graph_metabolism(&segment);
        let mut state = MetabolicState::default();
        let flux = gm.step(&mut state, 1.0, 1.0);
        // Should produce energy from external resource
        assert!(
            flux.consumed_external > 0.0,
            "should consume external resource"
        );
    }

    // ── validate_metabolic_graph tests ──

    #[test]
    fn validate_accepts_decoded_zero_genome() {
        let segment = [0.0f32; 16];
        let graph = decode_metabolic_graph(&segment);
        let entry = decode_entry_node_id(&segment, graph.nodes.len());
        assert!(validate_metabolic_graph(&graph, entry));
    }

    #[test]
    fn validate_accepts_decoded_random_genome() {
        let segment: [f32; 16] = [
            0.5, -0.3, 0.7, 0.2, -0.8, 0.1, 0.9, -0.5, 0.4, -0.7, 0.6, -0.2, 0.3, 0.8, 0.0, 0.0,
        ];
        let graph = decode_metabolic_graph(&segment);
        let entry = decode_entry_node_id(&segment, graph.nodes.len());
        assert!(validate_metabolic_graph(&graph, entry));
    }

    #[test]
    fn validate_rejects_empty_graph() {
        let graph = MetabolicGraph {
            nodes: vec![],
            edges: vec![],
        };
        assert!(!validate_metabolic_graph(&graph, 0));
    }

    #[test]
    fn validate_rejects_dangling_edge() {
        let graph = MetabolicGraph {
            nodes: vec![MetabolicNode {
                id: 0,
                catalytic_efficiency: 1.0,
            }],
            edges: vec![MetabolicEdge {
                from: 0,
                to: 99,
                flux_ratio: 0.5,
            }],
        };
        assert!(!validate_metabolic_graph(&graph, 0));
    }

    // ── CounterMetabolism tests ──

    #[test]
    fn counter_produces_bounded_energy() {
        let mut state = MetabolicState::default();
        let metabolism = CounterMetabolism::default();
        for _ in 0..100 {
            metabolism.step(&mut state, 1.0, 1.0);
        }
        assert!(
            (0.0..=metabolism.max_energy).contains(&state.energy),
            "energy out of bounds: {}",
            state.energy
        );
    }

    #[test]
    fn counter_consumes_external_resource() {
        let mut state = MetabolicState {
            energy: 0.0,
            resource: 0.0,
            waste: 0.0,
            ..MetabolicState::default()
        };
        let metabolism = CounterMetabolism::default();
        let flux = metabolism.step(&mut state, 1.0, 1.0);
        assert!(
            flux.consumed_external > 0.0,
            "should consume external resource"
        );
        assert!(state.energy > 0.0, "should produce energy");
    }

    #[test]
    fn counter_produces_no_waste() {
        let mut state = MetabolicState {
            energy: 0.0,
            resource: 0.0,
            waste: 0.0,
            ..MetabolicState::default()
        };
        let metabolism = CounterMetabolism::default();
        let flux = metabolism.step(&mut state, 1.0, 1.0);
        assert!(
            flux.produced_waste < f32::EPSILON,
            "counter should produce no waste"
        );
    }

    #[test]
    fn counter_flux_consumed_correctly() {
        let mut state = MetabolicState {
            energy: 0.0,
            ..MetabolicState::default()
        };
        let metabolism = CounterMetabolism {
            flat_efficiency: 1.0,
            energy_loss_rate: 0.0,
            ..CounterMetabolism::default()
        };
        let flux = metabolism.step(&mut state, 10.0, 1.0);
        // Energy gained should equal consumed * efficiency
        assert!(
            (state.energy - flux.consumed_external).abs() < f32::EPSILON,
            "energy {} should equal consumed {} * 1.0",
            state.energy,
            flux.consumed_external
        );
    }

    #[test]
    fn graph_uses_explicit_entry_node_id() {
        let mut state = MetabolicState {
            energy: 0.0,
            resource: 0.0,
            waste: 0.0,
            ..MetabolicState::default()
        };
        let metabolism = GraphMetabolism {
            graph: MetabolicGraph {
                nodes: vec![
                    MetabolicNode {
                        id: 10,
                        catalytic_efficiency: 0.0,
                    },
                    MetabolicNode {
                        id: 20,
                        catalytic_efficiency: 1.0,
                    },
                ],
                edges: Vec::new(),
            },
            conversion_efficiency: 1.0,
            waste_ratio: 0.0,
            energy_loss_rate: 0.0,
            max_energy: 10.0,
            entry_node_id: 20,
            edge_transfer_efficiency: 1.0,
            ..GraphMetabolism::default()
        };
        let _ = metabolism.step(&mut state, 1.0, 1.0);
        assert!(
            state.energy > 0.0,
            "entry node id should control external resource injection"
        );
    }
}
