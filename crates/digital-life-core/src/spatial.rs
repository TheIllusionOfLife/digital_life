use crate::agent::Agent;
use rstar::{RTree, RTreeObject, AABB};
use std::collections::HashSet;

/// Lightweight position-only struct for spatial indexing to avoid cloning full agents.
#[derive(Clone, Debug)]
pub struct AgentLocation {
    pub id: u32,
    pub position: [f64; 2],
}

impl RTreeObject for AgentLocation {
    type Envelope = AABB<[f64; 2]>;

    fn envelope(&self) -> Self::Envelope {
        AABB::from_point(self.position)
    }
}

/// Build an R*-tree from agent positions via bulk_load (O(n log n)).
pub fn build_index(agents: &[Agent]) -> RTree<AgentLocation> {
    let locations: Vec<AgentLocation> = agents
        .iter()
        .map(|a| AgentLocation {
            id: a.id,
            position: a.position,
        })
        .collect();
    RTree::bulk_load(locations)
}

/// Build an R*-tree from only active organisms.
pub fn build_index_active(agents: &[Agent], organism_alive: &[bool]) -> RTree<AgentLocation> {
    let active_count = agents
        .iter()
        .filter(|a| {
            organism_alive
                .get(a.organism_id as usize)
                .copied()
                .unwrap_or(false)
        })
        .count();
    let mut locations = Vec::with_capacity(active_count);
    for a in agents {
        if organism_alive
            .get(a.organism_id as usize)
            .copied()
            .unwrap_or(false)
        {
            locations.push(AgentLocation {
                id: a.id,
                position: a.position,
            });
        }
    }
    RTree::bulk_load(locations)
}

/// Count neighbors within `radius` of `center` (excludes agent with `self_id`).
/// Avoids allocation — returns count only.
pub fn count_neighbors(
    tree: &RTree<AgentLocation>,
    center: [f64; 2],
    radius: f64,
    self_id: u32,
    world_size: f64,
) -> usize {
    let mut count = 0usize;
    for_each_unique_neighbor(tree, center, radius, self_id, world_size, |_| {
        count += 1;
    });
    count
}

/// Query neighbors within `radius` of `center`, returning their agent IDs.
/// Uses AABB envelope query then filters by Euclidean distance.
/// Excludes the agent with `self_id`.
pub fn query_neighbors(
    tree: &RTree<AgentLocation>,
    center: [f64; 2],
    radius: f64,
    self_id: u32,
    world_size: f64,
) -> Vec<u32> {
    let mut result = Vec::new();
    for_each_unique_neighbor(tree, center, radius, self_id, world_size, |id| {
        result.push(id);
    });
    result.sort_unstable();
    result
}

fn for_each_unique_neighbor(
    tree: &RTree<AgentLocation>,
    center: [f64; 2],
    radius: f64,
    self_id: u32,
    world_size: f64,
    mut visitor: impl FnMut(u32),
) {
    assert!(
        world_size.is_finite() && world_size > 0.0,
        "world_size must be positive and finite"
    );
    let (x_offsets, x_len) = wrap_offsets(center[0], radius, world_size);
    let (y_offsets, y_len) = wrap_offsets(center[1], radius, world_size);
    let r_sq = radius * radius;

    // Fast path: no boundary wrapping means no duplicate candidates across envelopes.
    if x_len == 1 && y_len == 1 {
        let envelope = AABB::from_corners(
            [center[0] - radius, center[1] - radius],
            [center[0] + radius, center[1] + radius],
        );
        for loc in tree.locate_in_envelope(&envelope) {
            if loc.id == self_id {
                continue;
            }
            let dx = loc.position[0] - center[0];
            let dy = loc.position[1] - center[1];
            if dx * dx + dy * dy <= r_sq {
                visitor(loc.id);
            }
        }
        return;
    }

    let mut seen = HashSet::new();

    for &xoff in &x_offsets[..x_len] {
        for &yoff in &y_offsets[..y_len] {
            let translated = [center[0] + xoff, center[1] + yoff];
            let envelope = AABB::from_corners(
                [translated[0] - radius, translated[1] - radius],
                [translated[0] + radius, translated[1] + radius],
            );

            for loc in tree.locate_in_envelope(&envelope) {
                if loc.id == self_id {
                    continue;
                }
                let dx = wrapped_delta(loc.position[0] - center[0], world_size);
                let dy = wrapped_delta(loc.position[1] - center[1], world_size);
                if dx * dx + dy * dy <= r_sq && seen.insert(loc.id) {
                    visitor(loc.id);
                }
            }
        }
    }
}

fn wrap_offsets(coord: f64, radius: f64, world_size: f64) -> ([f64; 3], usize) {
    let mut offsets = [0.0; 3];
    let mut len = 1usize;
    if coord < radius {
        offsets[len] = world_size;
        len += 1;
    }
    if coord + radius >= world_size {
        offsets[len] = -world_size;
        len += 1;
    }
    (offsets, len)
}

fn wrapped_delta(delta: f64, world_size: f64) -> f64 {
    (delta + world_size / 2.0).rem_euclid(world_size) - world_size / 2.0
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_agent(id: u32, x: f64, y: f64) -> Agent {
        Agent::new(id, 0, [x, y])
    }

    #[test]
    fn query_finds_agents_within_radius() {
        let agents = vec![
            make_agent(0, 5.0, 5.0),
            make_agent(1, 6.0, 5.0),   // distance 1.0
            make_agent(2, 50.0, 50.0), // far away
        ];
        let tree = build_index(&agents);
        let result = query_neighbors(&tree, [5.0, 5.0], 2.0, u32::MAX, 100.0);
        assert_eq!(result, vec![0, 1]);
    }

    #[test]
    fn query_excludes_self() {
        let agents = vec![make_agent(0, 5.0, 5.0), make_agent(1, 6.0, 5.0)];
        let tree = build_index(&agents);
        let result = query_neighbors(&tree, [5.0, 5.0], 2.0, 0, 100.0);
        assert_eq!(result, vec![1]);
    }

    #[test]
    fn query_excludes_agents_outside_radius() {
        let agents = vec![make_agent(0, 0.0, 0.0), make_agent(1, 10.0, 10.0)];
        let tree = build_index(&agents);
        let result = query_neighbors(&tree, [0.0, 0.0], 1.0, u32::MAX, 100.0);
        assert_eq!(result, vec![0]);
    }

    #[test]
    fn query_returns_agent_ids_not_indices() {
        let agents = vec![make_agent(42, 1.0, 1.0), make_agent(99, 1.5, 1.0)];
        let tree = build_index(&agents);
        let result = query_neighbors(&tree, [1.0, 1.0], 2.0, u32::MAX, 100.0);
        assert_eq!(result, vec![42, 99]);
    }

    #[test]
    fn count_neighbors_excludes_self() {
        let agents = vec![
            make_agent(0, 5.0, 5.0),
            make_agent(1, 6.0, 5.0),
            make_agent(2, 50.0, 50.0),
        ];
        let tree = build_index(&agents);
        assert_eq!(count_neighbors(&tree, [5.0, 5.0], 2.0, 0, 100.0), 1);
    }

    #[test]
    fn count_neighbors_wraps_toroidally_across_world_edges() {
        // Assuming a world size of 100, x=99.8 and x=0.5 are only 0.7 apart.
        let agents = vec![make_agent(0, 0.5, 50.0), make_agent(1, 99.8, 50.0)];
        let tree = build_index(&agents);
        assert_eq!(count_neighbors(&tree, [0.5, 50.0], 1.0, 0, 100.0), 1);
    }

    #[test]
    fn query_neighbors_wraps_toroidally_at_corner() {
        let agents = vec![make_agent(0, 0.2, 0.2), make_agent(1, 99.8, 99.8)];
        let tree = build_index(&agents);
        let result = query_neighbors(&tree, [0.2, 0.2], 1.0, 0, 100.0);
        assert_eq!(result, vec![1]);
    }

    #[test]
    fn query_neighbors_returns_sorted_unique_ids() {
        let agents = vec![
            make_agent(10, 0.2, 50.0),
            make_agent(2, 99.9, 50.0),
            make_agent(7, 0.4, 50.0),
        ];
        let tree = build_index(&agents);
        let result = query_neighbors(&tree, [0.1, 50.0], 1.0, u32::MAX, 100.0);
        assert_eq!(result, vec![2, 7, 10]);
    }

    #[test]
    fn build_index_active_excludes_inactive_organisms() {
        let agents = vec![Agent::new(0, 0, [1.0, 1.0]), Agent::new(1, 1, [1.0, 1.2])];
        let tree = build_index_active(&agents, &[true, false]);
        let result = query_neighbors(&tree, [1.0, 1.0], 1.0, u32::MAX, 100.0);
        assert_eq!(result, vec![0]);
    }
}
