import type { Event, Frame, Hello, Inspect, Resource, ServerMessage, Status, Task } from './messages';

/** Client state rebuilt from protocol messages. Live and replay (B-11) feed the same reducer. */
export class World {
  hello: Hello | null = null;
  frame: Frame | null = null;
  tasks = new Map<string, Task>();
  resources = new Map<string, Resource>();
  events: Event[] = [];
  lines: { tick: number; speaker: string; text: string; session: string }[] = [];
  inspect = new Map<string, Inspect>();
  status: Status | null = null;
  error: string | null = null;

  apply(message: ServerMessage) {
    switch (message.type) {
      case 'hello':
        this.hello = message;
        this.frame = this.status = this.error = null;
        this.tasks = new Map(message.tasks.map(t => [t.id, t]));
        this.resources = new Map(message.resources.map(r => [r.id, r]));
        this.events = [];
        this.lines = [];
        this.inspect = new Map();
        break;
      case 'frame':
        this.frame = message;
        for (const t of message.tasks) this.tasks.set(t.id, t);
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
}
