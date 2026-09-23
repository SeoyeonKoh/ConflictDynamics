/** Protocol v1. IDs currently equal unique engine names; day/tick are zero-based.
 * Apply hello's full task/resource tables, then upsert each frame's deltas by id.
 * Reconnect resets state with hello and replays history before live messages.
 */
export interface Task {
  id: string; title: string; owner: string | null; progress: number;
  due: number; status: string; blocked_by: string[];
}
export interface Resource { id: string; holders: string[]; capacity: number }
export interface Hello {
  type: "hello"; version: 1; run_id: string; map: string;
  map_data: Record<string, unknown>; tick_minutes: number;
  agents: { id: string; name: string; sprite: string; dept: string | null }[];
  config: { ticks_per_day: number; max_days: number };
  tasks: Task[]; resources: Resource[];
}
export interface Frame {
  type: "frame"; tick: number; day: number; phase: string;
  agents: { id: string; place: string; x: number; y: number; action: string;
    expression: string; bubble?: string; session: string | null;
    /** Who a message or report is addressed to. */
    target?: string }[];
  /** Live sessions plus those that opened this tick, even if they already closed. */
  sessions: { id: string; kind: string; place: string | null; participants: string[] }[];
  tasks: Task[]; resources: Resource[];
}
export interface Event {
  type: "event"; tick: number;
  kind: "task" | "rejected" | "outcome" | "shock" | "session";
  actors: string[]; text: string; session: string | null; payload: Record<string, unknown>;
}
export interface Inspect {
  type: "inspect"; agent: string; tick: number; reflection: string[];
  state: { stress: number; mood: number };
  relationships: { to: string; relation: number; summary: string | null }[];
  retrieved: string[];
}
export interface Status {
  type: "status"; state: "running" | "paused" | "completed" | "failed";
  message: string; llm_usage: Record<string, unknown>;
}
export type Control =
  | { type: "control"; cmd: "pause" | "resume" | "step" }
  | { type: "control"; cmd: "speed"; value: number }
  | { type: "control"; cmd: "inspect"; agent: string };
export type ServerMessage = Hello | Frame | Event | Inspect | Status
  | { type: "error"; message: string };
