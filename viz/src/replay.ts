import type { Control, Hello, Inspect, ServerMessage } from './messages';
import type { World } from './world';

const lines = (text: string) => text.split('\n').filter(line => line.trim()).map(line => JSON.parse(line));

/**
 * Plays a finished run's `frames.jsonl` into World and answers the same controls as the live
 * socket, so the HUD and scene need no replay branch. Inspect reads `inspect.jsonl`: an agent's
 * panel at tick t is its last line with tick <= t, in file order.
 */
export class Replay {
  tick = -1;
  readonly last: number;
  private hello: Hello;
  private ticks: ServerMessage[][] = []; // per tick: its frame, then that tick's events
  private panels = new Map<string, Inspect[]>();
  private speed = 1;
  private timer: number | undefined;

  constructor(private world: World, journal: ServerMessage[], inspect: Inspect[], private changed: (tick: number) => void) {
    const [hello, ...rest] = journal;
    if (hello?.type !== 'hello') throw new Error('frames.jsonl does not start with hello');
    this.hello = hello;
    for (const message of rest) {
      if (message.type === 'frame') this.ticks[message.tick] = [message];
      else if (message.type === 'event') this.ticks[message.tick]?.push(message);
    }
    this.ticks = this.ticks.filter(Boolean); // a resumed run may leave gaps; keep order
    this.last = this.ticks.length - 1;
    for (const panel of inspect) {
      if (!this.panels.has(panel.agent)) this.panels.set(panel.agent, []);
      this.panels.get(panel.agent)!.push(panel);
    }
    world.apply(hello);
    this.seek(0);
    this.status('paused');
  }

  static async load(world: World, run: string, changed: (tick: number) => void) {
    const get = async (file: string) => {
      const response = await fetch(`/runs/${run}/${file}`);
      if (!response.ok) throw new Error(`${run}/${file}: ${response.status}`);
      return response.text();
    };
    const [frames, inspect] = await Promise.all([get('frames.jsonl'), get('inspect.jsonl').catch(() => '')]);
    return new Replay(world, lines(frames), lines(inspect), changed);
  }

  /** Index into the recorded ticks (not the engine tick, which a resume may offset). */
  seek(index: number) {
    index = Math.max(0, Math.min(this.last, index));
    if (index !== this.tick + 1) {
      const status = this.world.status;
      this.world.apply(this.hello); // a jump rebuilds from the start and snaps
      if (status) this.world.apply(status);
      for (let i = 0; i < index; i++) this.ticks[i].forEach(m => this.world.apply(m));
    }
    this.ticks[index].forEach(m => this.world.apply(m));
    this.tick = index;
    if (index === this.last) this.stop();
    this.changed(this.tick);
  }

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
