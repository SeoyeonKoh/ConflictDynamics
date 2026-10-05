import type { EngineEvent, Event, Frame, Hello, Inspect, Resource, ServerMessage, Status, Task } from './messages';

/** Client state rebuilt from protocol messages. Live and replay (B-11) feed the same reducer. */
export class World {
  hello: Hello | null = null;
  frame: Frame | null = null;
  tasks = new Map<string, Task>();
  /** Prerequisites per task: `depends_on` when sent, else every `blocked_by` seen (older runs). */
  deps = new Map<string, Set<string>>();
  resources = new Map<string, Resource>();
  events: Event[] = [];
  lines: { tick: number; speaker: string; text: string; session: string }[] = [];
  inspect = new Map<string, Inspect>();
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
        this.inspect = new Map();
        break;
      case 'frame':
        this.frame = message;
        for (const t of message.tasks) {
          this.tasks.set(t.id, t);
          this.noteDeps(t);
        }
        for (const r of message.resources) this.resources.set(r.id, r);
        for (const line of message.lines ?? []) this.lines.push({ tick: message.tick, ...line });
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

  private noteDeps(t: Task) {
    const known = this.deps.get(t.id) ?? new Set<string>();
    for (const d of t.depends_on ?? t.blocked_by) known.add(d);
    this.deps.set(t.id, known);
  }
}
