import type { Line, SessionInfo } from './conversations';
import type { EngineEvent, Event, Frame, Hello, Inspect, PlanItem, Resource, ServerMessage, Status, Task } from './messages';

/** A plan block with the tick it starts at (the end of the block before it). */
export interface Block extends PlanItem { start: number }

/** Client state rebuilt from protocol messages. Live and replay (B-11) feed the same reducer. */
export class World {
  hello: Hello | null = null;
  frame: Frame | null = null;
  tasks = new Map<string, Task>();
  /** Prerequisites per task: `depends_on` when sent, else every `blocked_by` seen (older runs). */
  deps = new Map<string, Set<string>>();
  resources = new Map<string, Resource>();
  events: Event[] = [];
  lines: Line[] = [];
  /** Every conversation seen so far: kind, place and members (frames list only open ones). */
  sessions = new Map<string, SessionInfo>();
  /** Names and titles: from hello, or for older journals from conflict-server. */
  people = new Map<string, { name: string; title: string | null }>();
  inspect = new Map<string, Inspect>();
  /** Each agent's plan for the day on screen: blocks already run, then the plan as it stands. */
  plans = new Map<string, Block[]>();
  status: Status | null = null;
  /** A replay's engine log, loaded once; hello leaves it alone. */
  engineEvents: EngineEvent[] = [];
  error: string | null = null;

  apply(message: ServerMessage) {
    switch (message.type) {
      case 'hello':
        this.hello = message;
        this.frame = this.status = this.error = null;
        this.tasks = new Map(message.tasks.map(t => [t.id, t]));
        this.deps = new Map();
        for (const t of message.tasks) this.noteDeps(t);
        this.resources = new Map(message.resources.map(r => [r.id, r]));
        this.events = [];
        this.lines = [];
        this.sessions = new Map();
        for (const a of message.agents) {
          if (a.display_name) this.people.set(a.id, { name: a.display_name, title: a.title ?? null });
        }
        this.inspect = new Map();
        this.plans = new Map();
        break;
      case 'frame':
        this.frame = message;
        for (const t of message.tasks) {
          this.tasks.set(t.id, t);
          this.noteDeps(t);
        }
        for (const r of message.resources) this.resources.set(r.id, r);
        for (const a of message.agents) if (a.plan) this.notePlan(a.id, a.plan, message.tick);
        for (const line of message.lines ?? []) this.lines.push({ tick: message.tick, ...line });
        for (const s of message.sessions) {
          if (!this.sessions.has(s.id)) this.sessions.set(s.id, { kind: s.kind, place: s.place, participants: [...s.participants] });
        }
        break;
      case 'event':
        this.events.push(message);
        break;
      case 'inspect':
        this.inspect.set(message.agent, message);
        break;
      case 'status':
        this.status = message;
        break;
      case 'error':
        this.error = message.message;
        break;
    }
  }

  /** A new plan (made at arrival, or re-made) keeps today's finished blocks and replaces the rest. */
  private notePlan(agent: string, plan: PlanItem[], tick: number) {
    const span = this.hello?.config.ticks_per_day ?? 32;
    const day = Math.floor(tick / span) * span;
    const kept = (this.plans.get(agent) ?? []).filter(b => b.start >= day && b.until <= tick);
    let start = kept.at(-1)?.until ?? Math.min(tick, plan[0]?.until ?? tick);
    const blocks: Block[] = [...kept];
    for (const item of plan) {
      if (item.until <= start) continue;
      blocks.push({ ...item, start });
      start = item.until;
    }
    this.plans.set(agent, blocks);
  }

  private noteDeps(t: Task) {
    const known = this.deps.get(t.id) ?? new Set<string>();
    for (const d of t.depends_on ?? t.blocked_by) known.add(d);
    this.deps.set(t.id, known);
  }
}
