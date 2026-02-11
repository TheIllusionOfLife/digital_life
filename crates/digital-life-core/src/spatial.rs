use crate::agent::Agent;
use rstar::{RTree, AABB};

/// Build an R*-tree from agents via bulk_load (O(n log n)).
pub fn build_index(agents: &[Agent]) -> RTree<Agent> {
    RTree::bulk_load(agents.to_vec())
}

/// Query neighbors within `radius` of `center`, returning their indices in the original slice.
/// Uses AABB envelope query then filters by Euclidean distance.
pub fn query_neighbors(
    tree: &RTree<Agent>,
    center: [f64; 2],
    radius: f64,
) -> Vec<u32> {
    let envelope = AABB::from_corners(
        [center[0] - radius, center[1] - radius],
        [center[0] + radius, center[1] + radius],
    );
    let r_sq = radius * radius;

    tree.locate_in_envelope(&envelope)
        .filter(|agent| {
            let dx = agent.position[0] - center[0];
            let dy = agent.position[1] - center[1];
            dx * dx + dy * dy <= r_sq
        })
        .map(|agent| agent.id)
        .collect()
}
