/** Protocol v1. IDs currently equal unique engine names; day/tick are zero-based.
 * Apply hello's full task/resource tables, then upsert each frame's deltas by id.
 * Reconnect resets state with hello and replays history before live messages.
 */
export interface Task {
  id: string; title: string; owner: string | null; progress: number;
  due: number; status: string; blocked_by: string[];
  /** The department project it belongs to ("P1 payments service"); none for the core release. */
  group?: string | null;
  /** Every prerequisite, finished or not (blocked_by lists only the unfinished ones). */
  depends_on?: string[];
  /** A step done for another department's project. */
  cross?: boolean;
  /** ready · in_progress · review · done (status folds in blocked/overdue). */
  lifecycle?: string;
  /** For a task that produces a document: its expected form, and what review checks. */
  deliverable?: string | null;
  criteria?: string | null;
  /** The evidence on file so far: the engine's `Org.record`. Absent in older recordings. */
  record?: TaskRecord;
}
export interface TaskRecord {
  owner: string | null; team: string[]; worked_by: Record<string, number>;
  started_tick: number | null; review_tick: number | null; done_tick: number | null;
  due: number; on_time: boolean; approved_by: string | null; approval_note: string | null;
  rejections: { by: string; tick: number; note: string | null }[];
  summary: string | null; document: string | null;
  prerequisites: { id: string; done_tick: number | null; approved_by: string | null }[];
  handoff_to: string[];
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
  /** Every utterance this tick in order (talk, live and async DM); absent when nobody spoke. */
  lines?: { speaker: string; text: string; session: string }[];
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
/** One line of a run's `events.jsonl` (the engine log, not the socket's `event`): replays of
 * recordings made before frames carried `task.record` rebuild the evidence from it. */
export interface EngineEvent {
  tick: number; kind: string; actor: string | null; target: string | null;
  payload: Record<string, unknown>;
}
