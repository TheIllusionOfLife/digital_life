use super::decode_organism_metabolism;
use super::metrics::{LineageEvent, StepTimings};
use super::World;
use crate::agent::Agent;
use crate::config::SimConfig;
use crate::metabolism::MetabolicState;
use crate::nn::NeuralNet;
use crate::organism::{DevelopmentalProgram, OrganismRuntime};
use crate::spatial::{self, AgentLocation};
use rand::Rng;
use rstar::RTree;
use std::f64::consts::PI;
use std::time::Instant;

impl World {
    fn terminal_boundary_threshold(&self) -> f32 {
        self.config
            .boundary_collapse_threshold
            .max(self.config.death_boundary_threshold)
    }

    fn next_agent_id_checked(&mut self) -> Option<u32> {
        if self.next_agent_id == u32::MAX {
            return None;
        }
        let id = self.next_agent_id;
        self.next_agent_id += 1;
        Some(id)
    }

    pub(crate) fn prune_dead_entities(&mut self) {
        if self.organisms.iter().all(|o| o.alive) {
            return;
        }

        let old_organisms = std::mem::take(&mut self.organisms);
        let mut remap = vec![None::<u16>; old_organisms.len()];
        let mut new_organisms = Vec::with_capacity(old_organisms.len());
        for (old_idx, mut org) in old_organisms.into_iter().enumerate() {
            if !org.alive {
                continue;
            }
            let new_id = new_organisms.len() as u16;
            remap[old_idx] = Some(new_id);
            org.id = new_id;
            org.agent_ids.clear();
            new_organisms.push(org);
        }

        let old_agents = std::mem::take(&mut self.agents);
        let mut new_agents = Vec::with_capacity(old_agents.len());
        for mut agent in old_agents {
            if let Some(new_org_id) = remap
                .get(agent.organism_id as usize)
                .and_then(|mapped| *mapped)
            {
                agent.organism_id = new_org_id;
                new_agents.push(agent);
            }
        }

        self.organisms = new_organisms;
        self.agents = new_agents;
        for agent in &self.agents {
            self.organisms[agent.organism_id as usize]
                .agent_ids
                .push(agent.id);
        }
        self.org_toroidal_sums
            .resize(self.organisms.len(), [0.0, 0.0, 0.0, 0.0]);
        self.org_counts.resize(self.organisms.len(), 0);
        self.org_toroidal_sums.fill([0.0, 0.0, 0.0, 0.0]);
        self.org_counts.fill(0);
    }

    /// Effective sensing radius for an organism, accounting for developmental stage.
    pub(crate) fn effective_sensing_radius(&self, org_idx: usize) -> f64 {
        let dev_sensing = if self.config.enable_growth {
            self.organisms[org_idx]
                .developmental_program
                .stage_factors(self.organisms[org_idx].maturity)
                .1
        } else {
            1.0
        };
        self.config.sensing_radius * dev_sensing as f64
    }

    fn mark_dead(&mut self, org_idx: usize) {
        if let Some(org) = self.organisms.get_mut(org_idx) {
            if org.alive {
                self.lifespans.push(org.age_steps);
                org.alive = false;
                org.boundary_integrity = 0.0;
                self.deaths_last_step += 1;
                self.total_deaths += 1;
            }
        }
    }

    fn maybe_reproduce(&mut self) {
        let child_agents =
            (self.config.agents_per_organism / 2).max(self.config.reproduction_child_min_agents);
        let parent_indices: Vec<usize> = self
            .organisms
            .iter()
            .enumerate()
            .filter_map(|(idx, org)| {
                let mature_enough = org.maturity >= 1.0;
                (org.alive
                    && org.metabolic_state.energy >= self.config.reproduction_min_energy
                    && org.boundary_integrity >= self.config.reproduction_min_boundary
                    && mature_enough)
                    .then_some(idx)
            })
            .collect();
        if parent_indices.is_empty() {
            return;
        }
        let centers = self.compute_organism_centers();

        for parent_idx in parent_indices {
            if self
                .agents
                .len()
                .checked_add(child_agents)
                .map(|n| n > SimConfig::MAX_TOTAL_AGENTS)
                .unwrap_or(true)
            {
                break;
            }
            let remaining_ids = u32::MAX as u64 - self.next_agent_id as u64;
            if remaining_ids + 1 < child_agents as u64 {
                self.agent_id_exhaustions_last_step += 1;
                self.total_agent_id_exhaustions += 1;
                break;
            }

            let center = centers
                .get(parent_idx)
                .and_then(|c| *c)
                .unwrap_or([0.0, 0.0]);
            let (parent_generation, parent_stable_id, parent_ancestor, mut child_genome) = {
                let parent = &self.organisms[parent_idx];
                if !parent.alive
                    || parent.metabolic_state.energy < self.config.reproduction_energy_cost
                {
                    continue;
                }
                (
                    parent.generation,
                    parent.stable_id,
                    parent.ancestor_genome.clone(),
                    parent.genome.clone(),
                )
            };

            self.organisms[parent_idx].metabolic_state.energy -=
                self.config.reproduction_energy_cost;

            if self.config.enable_evolution {
                child_genome.mutate(&mut self.rng, &self.mutation_rates);
            }
            let child_weights = if child_genome.nn_weights().len() == NeuralNet::WEIGHT_COUNT {
                child_genome.nn_weights().to_vec()
            } else {
                self.organisms[parent_idx].nn.to_weight_vec()
            };
            let child_nn = NeuralNet::from_weights(child_weights.into_iter());
            let child_id = match u16::try_from(self.organisms.len()) {
                Ok(id) => id,
                Err(_) => break,
            };
            let mut child_agent_ids = Vec::with_capacity(child_agents);

            for _ in 0..child_agents {
                let theta = self.rng.random::<f64>() * 2.0 * PI;
                let radius =
                    self.rng.random::<f64>().sqrt() * self.config.reproduction_spawn_radius;
                let pos = [
                    (center[0] + radius * theta.cos()).rem_euclid(self.config.world_size),
                    (center[1] + radius * theta.sin()).rem_euclid(self.config.world_size),
                ];
                let Some(id) = self.next_agent_id_checked() else {
                    break;
                };
                let mut agent = Agent::new(id, child_id, pos);
                agent.internal_state[2] = 1.0;
                child_agent_ids.push(id);
                self.agents.push(agent);
            }
            if child_agent_ids.is_empty() {
                break;
            }

            let metabolic_state = MetabolicState {
                energy: self.config.reproduction_energy_cost,
                ..MetabolicState::default()
            };
            let child_metabolism_engine =
                decode_organism_metabolism(&child_genome, self.config.metabolism_mode);
            let developmental_program = DevelopmentalProgram::decode(child_genome.segment_data(3));
            let child_stable_id = self.next_organism_stable_id;
            let child_generation = parent_generation + 1;
            let child = OrganismRuntime {
                id: child_id,
                stable_id: child_stable_id,
                generation: child_generation,
                age_steps: 0,
                alive: true,
                boundary_integrity: 1.0,
                metabolic_state,
                genome: child_genome,
                ancestor_genome: parent_ancestor,
                nn: child_nn,
                agent_ids: child_agent_ids,
                maturity: 0.0,
                metabolism_engine: child_metabolism_engine,
                developmental_program,
                parent_stable_id: Some(parent_stable_id),
            };
            self.next_organism_stable_id = self.next_organism_stable_id.saturating_add(1);
            self.lineage_events.push(LineageEvent {
                step: self.step_index,
                parent_stable_id,
                child_stable_id,
                generation: child_generation,
            });
            self.organisms.push(child);
            self.org_toroidal_sums.push([0.0, 0.0, 0.0, 0.0]);
            self.org_counts.push(0);
            self.births_last_step += 1;
            self.total_births += 1;
        }
    }

    /// Compute neighbor-informed neural deltas for all agents.
    fn step_nn_query_phase(
        &self,
        tree: &RTree<AgentLocation>,
    ) -> (Vec<[f32; 4]>, Vec<f32>, Vec<usize>) {
        let mut deltas: Vec<[f32; 4]> = Vec::with_capacity(self.agents.len());
        let mut neighbor_sums = vec![0.0f32; self.organisms.len()];
        let mut neighbor_counts = vec![0usize; self.organisms.len()];

        for agent in &self.agents {
            let org_idx = agent.organism_id as usize;
            if !self
                .organisms
                .get(org_idx)
                .map(|o| o.alive)
                .unwrap_or(false)
            {
                deltas.push([0.0; 4]);
                continue;
            }
            let effective_radius = self.effective_sensing_radius(org_idx);
            let neighbor_count = spatial::count_neighbors(
                tree,
                agent.position,
                effective_radius,
                agent.id,
                self.config.world_size,
            );

            neighbor_sums[org_idx] += neighbor_count as f32;
            neighbor_counts[org_idx] += 1;

            let input: [f32; 8] = [
                (agent.position[0] / self.config.world_size) as f32,
                (agent.position[1] / self.config.world_size) as f32,
                (agent.velocity[0] / self.config.max_speed) as f32,
                (agent.velocity[1] / self.config.max_speed) as f32,
                agent.internal_state[0],
                agent.internal_state[1],
                agent.internal_state[2],
                neighbor_count as f32 / self.config.neighbor_norm as f32,
            ];
            let nn = &self.organisms[org_idx].nn;
            deltas.push(nn.forward(&input));
        }

        (deltas, neighbor_sums, neighbor_counts)
    }

    /// Apply movement + homeostasis updates for each alive agent and gather
    /// aggregates consumed by boundary + metabolism phases.
    fn step_agent_state_phase(&mut self, deltas: &[[f32; 4]]) -> (Vec<f32>, Vec<usize>) {
        self.org_toroidal_sums.fill([0.0, 0.0, 0.0, 0.0]);
        self.org_counts.fill(0);
        let world_size = self.config.world_size;
        let tau_over_world = (2.0 * PI) / world_size;
        let mut homeostasis_sums = vec![0.0f32; self.organisms.len()];
        let mut homeostasis_counts = vec![0usize; self.organisms.len()];

        for (agent, delta) in self.agents.iter_mut().zip(deltas.iter()) {
            let org_idx = agent.organism_id as usize;
            if !self.organisms[org_idx].alive {
                agent.velocity = [0.0, 0.0];
                continue;
            }
            // Expose boundary with a one-step lag to avoid an extra full pass.
            agent.internal_state[2] = self.organisms[org_idx].boundary_integrity;

            if self.config.enable_response {
                agent.velocity[0] += delta[0] as f64 * self.config.dt;
                agent.velocity[1] += delta[1] as f64 * self.config.dt;
            }

            let speed_sq =
                agent.velocity[0] * agent.velocity[0] + agent.velocity[1] * agent.velocity[1];
            if speed_sq > self.config.max_speed * self.config.max_speed {
                let scale = self.config.max_speed / speed_sq.sqrt();
                agent.velocity[0] *= scale;
                agent.velocity[1] *= scale;
            }

            agent.position[0] = (agent.position[0] + agent.velocity[0] * self.config.dt)
                .rem_euclid(self.config.world_size);
            agent.position[1] = (agent.position[1] + agent.velocity[1] * self.config.dt)
                .rem_euclid(self.config.world_size);

            let h_decay = self.config.homeostasis_decay_rate * self.config.dt as f32;
            agent.internal_state[0] = (agent.internal_state[0] - h_decay).max(0.0);
            agent.internal_state[1] = (agent.internal_state[1] - h_decay).max(0.0);

            if self.config.enable_homeostasis {
                agent.internal_state[0] =
                    (agent.internal_state[0] + delta[2] * self.config.dt as f32).clamp(0.0, 1.0);
                agent.internal_state[1] =
                    (agent.internal_state[1] + delta[3] * self.config.dt as f32).clamp(0.0, 1.0);
            }

            homeostasis_sums[org_idx] += agent.internal_state[0];
            homeostasis_counts[org_idx] += 1;

            let theta_x = agent.position[0] * tau_over_world;
            let theta_y = agent.position[1] * tau_over_world;
            self.org_toroidal_sums[org_idx][0] += theta_x.sin();
            self.org_toroidal_sums[org_idx][1] += theta_x.cos();
            self.org_toroidal_sums[org_idx][2] += theta_y.sin();
            self.org_toroidal_sums[org_idx][3] += theta_y.cos();
            self.org_counts[org_idx] += 1;
        }
        (homeostasis_sums, homeostasis_counts)
    }

    /// Update boundary integrity using homeostasis aggregates from the state phase.
    fn step_boundary_phase(
        &mut self,
        homeostasis_sums: &[f32],
        homeostasis_counts: &[usize],
        boundary_terminal_threshold: f32,
    ) {
        if !self.config.enable_boundary_maintenance {
            return;
        }

        let dt = self.config.dt as f32;
        let mut to_kill = Vec::new();
        for (org_idx, org) in self.organisms.iter_mut().enumerate() {
            if !org.alive {
                org.boundary_integrity = 0.0;
                continue;
            }

            let energy_deficit =
                (self.config.metabolic_viability_floor - org.metabolic_state.energy).max(0.0);
            let decay = self.config.boundary_decay_base_rate
                + self.config.boundary_decay_energy_scale
                    * (energy_deficit
                        + org.metabolic_state.waste * self.config.boundary_waste_pressure_scale);
            let homeostasis_factor = if homeostasis_counts[org_idx] > 0 {
                homeostasis_sums[org_idx] / homeostasis_counts[org_idx] as f32
            } else {
                0.5
            };
            let dev_boundary = if self.config.enable_growth {
                org.developmental_program.stage_factors(org.maturity).0
            } else {
                1.0
            };
            let repair = (org.metabolic_state.energy
                - org.metabolic_state.waste
                    * self.config.boundary_waste_pressure_scale
                    * self.config.boundary_repair_waste_penalty_scale)
                .max(0.0)
                * self.config.boundary_repair_rate
                * homeostasis_factor
                * dev_boundary;
            org.boundary_integrity =
                (org.boundary_integrity - decay * dt + repair * dt).clamp(0.0, 1.0);
            if org.boundary_integrity <= boundary_terminal_threshold {
                to_kill.push(org_idx);
            }
        }
        for org_idx in to_kill {
            self.mark_dead(org_idx);
        }
    }

    /// Update per-organism metabolism and consume resource field.
    fn step_metabolism_phase(&mut self, boundary_terminal_threshold: f32) {
        if !self.config.enable_metabolism {
            return;
        }
        let world_size = self.config.world_size;

        let mut to_kill = Vec::new();
        for (org_idx, org) in self.organisms.iter_mut().enumerate() {
            if !org.alive {
                continue;
            }
            let center = if self.org_counts[org_idx] > 0 {
                [
                    Self::toroidal_mean_coord(
                        self.org_toroidal_sums[org_idx][0],
                        self.org_toroidal_sums[org_idx][1],
                        world_size,
                    ),
                    Self::toroidal_mean_coord(
                        self.org_toroidal_sums[org_idx][2],
                        self.org_toroidal_sums[org_idx][3],
                        world_size,
                    ),
                ]
            } else {
                [0.0, 0.0]
            };
            let external = self.resource_field.get(center[0], center[1]);
            let pre_energy = org.metabolic_state.energy;
            let engine = org.metabolism_engine.as_ref().unwrap_or(&self.metabolism);
            let flux = engine.step(&mut org.metabolic_state, external, self.config.dt as f32);
            let energy_delta = org.metabolic_state.energy - pre_energy;
            if energy_delta > 0.0 {
                let growth_factor = if self.config.enable_growth {
                    org.developmental_program.stage_factors(org.maturity).2
                } else {
                    self.config.growth_immature_metabolic_efficiency
                        + org.maturity * (1.0 - self.config.growth_immature_metabolic_efficiency)
                };
                org.metabolic_state.energy = pre_energy
                    + energy_delta * growth_factor * self.config.metabolism_efficiency_multiplier;
            }
            if flux.consumed_external > 0.0 {
                let _ = self
                    .resource_field
                    .take(center[0], center[1], flux.consumed_external);
            }

            if org.metabolic_state.energy <= self.config.death_energy_threshold
                || org.boundary_integrity <= boundary_terminal_threshold
            {
                to_kill.push(org_idx);
            }
        }
        for org_idx in to_kill {
            self.mark_dead(org_idx);
        }
    }

    /// Update age, growth stage, and crowding effects, then mark deaths.
    fn step_growth_and_crowding_phase(
        &mut self,
        neighbor_sums: &[f32],
        neighbor_counts: &[usize],
        boundary_terminal_threshold: f32,
    ) {
        let mut to_kill = Vec::new();
        for (org_idx, org) in self.organisms.iter_mut().enumerate() {
            if !org.alive {
                continue;
            }
            org.age_steps = org.age_steps.saturating_add(1);
            if org.age_steps > self.config.max_organism_age_steps {
                to_kill.push(org_idx);
                continue;
            }

            if self.config.enable_growth && org.maturity < 1.0 {
                let base_rate = 1.0 / self.config.growth_maturation_steps as f32;
                let rate = base_rate * org.developmental_program.maturation_rate_modifier;
                org.maturity = (org.maturity + rate).min(1.0);
            }

            let avg_neighbors = if neighbor_counts[org_idx] > 0 {
                neighbor_sums[org_idx] / neighbor_counts[org_idx] as f32
            } else {
                0.0
            };
            if avg_neighbors > self.config.crowding_neighbor_threshold {
                let excess = avg_neighbors - self.config.crowding_neighbor_threshold;
                org.boundary_integrity = (org.boundary_integrity
                    - excess * self.config.crowding_boundary_decay * self.config.dt as f32)
                    .clamp(0.0, 1.0);
            }
            if org.boundary_integrity <= boundary_terminal_threshold {
                to_kill.push(org_idx);
            }
        }
        for org_idx in to_kill {
            self.mark_dead(org_idx);
        }
    }

    /// Apply optional sham work and environment updates.
    fn step_environment_phase(&mut self, tree: &RTree<AgentLocation>) {
        if self.config.enable_sham_process {
            let mut _sham_sum: f64 = 0.0;
            for agent in &self.agents {
                let org_idx = agent.organism_id as usize;
                if !self.organisms.get(org_idx).is_some_and(|o| o.alive) {
                    continue;
                }
                let effective_radius = self.effective_sensing_radius(org_idx);
                let neighbor_count = spatial::count_neighbors(
                    tree,
                    agent.position,
                    effective_radius,
                    agent.id,
                    self.config.world_size,
                );
                _sham_sum += neighbor_count as f64;
            }
        }

        if self.config.environment_shift_step > 0
            && self.step_index == self.config.environment_shift_step
        {
            self.current_resource_rate = self.config.environment_shift_resource_rate;
        }

        if self.config.environment_cycle_period > 0 {
            let phase = (self.step_index / self.config.environment_cycle_period) % 2;
            self.current_resource_rate = if phase == 0 {
                self.config.resource_regeneration_rate
            } else {
                self.config.environment_cycle_low_rate
            };
        }

        if self.current_resource_rate > 0.0 {
            self.resource_field
                .regenerate(self.current_resource_rate * self.config.dt as f32);
        }
    }

    pub fn step(&mut self) -> StepTimings {
        let total_start = Instant::now();
        self.step_index = self.step_index.saturating_add(1);
        self.births_last_step = 0;
        self.deaths_last_step = 0;
        self.agent_id_exhaustions_last_step = 0;
        let boundary_terminal_threshold = self.terminal_boundary_threshold();

        let t0 = Instant::now();
        let live_flags = self.live_flags();
        let tree = spatial::build_index_active(&self.agents, &live_flags);
        let spatial_build_us = t0.elapsed().as_micros() as u64;

        let t1 = Instant::now();
        let (deltas, neighbor_sums, neighbor_counts) = self.step_nn_query_phase(&tree);
        let nn_query_us = t1.elapsed().as_micros() as u64;

        let t2 = Instant::now();
        let (homeostasis_sums, homeostasis_counts) = self.step_agent_state_phase(&deltas);
        self.step_boundary_phase(
            &homeostasis_sums,
            &homeostasis_counts,
            boundary_terminal_threshold,
        );
        self.step_metabolism_phase(boundary_terminal_threshold);
        self.step_growth_and_crowding_phase(
            &neighbor_sums,
            &neighbor_counts,
            boundary_terminal_threshold,
        );

        if self.config.enable_reproduction {
            self.maybe_reproduce();
        }
        let dead_count = self.organisms.iter().filter(|o| !o.alive).count();
        if dead_count > 0
            && (self
                .step_index
                .is_multiple_of(self.config.compaction_interval_steps)
                || dead_count * 4 >= self.organisms.len().max(1))
        {
            self.prune_dead_entities();
        }

        self.step_environment_phase(&tree);

        let state_update_us = t2.elapsed().as_micros() as u64;

        StepTimings {
            spatial_build_us,
            nn_query_us,
            state_update_us,
            total_us: total_start.elapsed().as_micros() as u64,
        }
    }
}
