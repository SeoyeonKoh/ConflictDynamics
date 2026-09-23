import type { Control, Hello, Inspect, ServerMessage } from './messages';
import type { World } from './world';

const lines = (text: string) => text.split('\n').filter(line => line.trim()).map(line => JSON.parse(line));

/**
 * A journal of protocol messages that can put World at any recorded tick. Replay fills it from a
 * finished run's `frames.jsonl`; live mode records the socket into it so earlier ticks can be
 * reviewed while the run goes on. Inspect answers from recorded panels: an agent's panel at tick t
 * is its last one with tick <= t (`inspect.jsonl` in replay, the socket's replies in live).
 */
export class Replay {
  tick = -1; // the recorded tick World shows
  private hello: Hello | null = null;
  private ticks: ServerMessage[][] = []; // per tick: its frame, then that tick's events
  private panels = new Map<string, Inspect[]>();
  private speed = 1;
  private timer: number | undefined;

  constructor(private world: World, private changed: (tick: number) => void) {}

  get last() {
    return this.ticks.length - 1;
  }

  static async load(world: World, run: string, changed: (tick: number) => void) {
    const get = async (file: string) => {
      const response = await fetch(`/runs/${run}/${file}`);
      if (!response.ok) throw new Error(`${run}/${file}: ${response.status}`);
      return response.text();
    };
    const [frames, inspect] = await Promise.all([get('frames.jsonl'), get('inspect.jsonl').catch(() => '')]);
    const replay = new Replay(world, changed);
    // A resumed run's journal continues after its checkpoint; only the first hello starts it.
    const journal: ServerMessage[] = lines(frames);
    journal.filter((m, i) => m.type !== 'hello' || i === 0).forEach(m => replay.record(m));
    lines(inspect).forEach(m => replay.record(m));
    if (!replay.hello) throw new Error('frames.jsonl does not start with hello');
    world.apply(replay.hello);
    replay.seek(0);
    replay.status('paused');
    return replay;
  }

  /** Journals a message without showing it; a hello starts a new journal. */
  record(message: ServerMessage) {
    switch (message.type) {
      case 'hello':
        this.hello = message;
        this.ticks = [];
        this.panels = new Map();
        this.tick = -1;
        break;
      case 'frame':
        this.ticks.push([message]);
        break;
      case 'event':
        this.ticks.at(-1)?.push(message);
        break;
      case 'inspect':
        if (!this.panels.has(message.agent)) this.panels.set(message.agent, []);
        this.panels.get(message.agent)!.push(message);
        break;
    }
  }

  /** Live mode applied the latest messages itself; World now shows the last recorded tick. */
  followed() {
    this.tick = this.last;
  }

  /** Index into the recorded ticks (not the engine tick, which a resume may offset). */
  seek(index: number) {
    if (!this.hello || this.last < 0) return;
    index = Math.max(0, Math.min(this.last, index));
    if (index !== this.tick + 1) {
      const status = this.world.status;
      this.world.apply(this.hello); // a jump rebuilds from the start and snaps
      if (status) this.world.apply(status);
      for (let i = 0; i < index; i++) this.ticks[i].forEach(m => this.world.apply(m));
    }
    this.ticks[index].forEach(m => this.world.apply(m));
    this.tick = index;
    if (index === this.last && this.timer !== undefined) this.stop();
    this.changed(this.tick);
  }

  /** Replay's answer to the controls the live socket takes; live review uses only `inspect`. */
  handle(control: Control) {
    switch (control.cmd) {
      case 'resume': return this.play();
      case 'pause': return this.stop();
      case 'step': this.stop(); return this.seek(this.tick + 1);
      case 'speed':
        this.speed = control.value;
        if (this.timer !== undefined) this.play();
        return;
      case 'inspect': {
        const now = this.world.frame?.tick ?? 0;
        const panel = this.panels.get(control.agent)?.filter(p => p.tick <= now).at(-1);
        if (panel) this.world.apply(panel);
        return this.changed(this.tick);
      }
    }
  }

  private play() {
    clearInterval(this.timer);
    if (this.tick === this.last) this.seek(0);
    this.timer = setInterval(() => this.seek(this.tick + 1), 1000 / this.speed);
    this.status('running');
  }

  private stop() {
    clearInterval(this.timer);
    this.timer = undefined;
    this.status('paused');
  }

  private status(state: 'running' | 'paused') {
    this.world.apply({ type: 'status', state, message: 'replay', llm_usage: {} });
    this.changed(this.tick);
  }
}
