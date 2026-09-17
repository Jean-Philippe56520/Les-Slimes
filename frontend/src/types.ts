export interface WorldSummary {
  tick: number;
  population: number;
  food_count: number;
  births: number;
  deaths: number;
  mean_energy: number;
  mean_health: number;
  max_generation: number;
  state_digest: string;
  width: number;
  height: number;
}

export interface SlimeProjection {
  id: string;
  parent_id: string | null;
  generation: number;
  x: number;
  y: number;
  heading: number;
  energy: number;
  health: number;
  age_ticks: number;
  current_action: string;
  alive: boolean;
}

export interface SlimeCollection {
  tick: number;
  slimes: SlimeProjection[];
}

export interface FoodProjection {
  id: number;
  x: number;
  y: number;
  nutrition: number;
}

export interface FoodCollection {
  tick: number;
  foods: FoodProjection[];
}

export interface WriterLeaseHealth {
  valid: boolean;
  holder_id: string | null;
  generation: number | null;
  expires_at_utc: string | null;
}

export interface RuntimeHealth {
  status: string;
  world_tick: number;
  last_simulated_at_utc: string;
  wall_clock_utc: string;
  lag_seconds: number;
  ticks_due: number;
  pending_commands: number;
  oldest_pending_command_utc: string | null;
  writer_lease: WriterLeaseHealth;
}

export interface CanonicalSnapshot {
  world: WorldSummary;
  slimes: SlimeCollection;
  foods: FoodCollection;
  health: RuntimeHealth;
  receivedAt: number;
}
