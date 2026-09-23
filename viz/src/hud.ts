import type { Link } from './connection';
import type { Control, Event } from './messages';
import type { World } from './world';

const $ = (id: string) => document.getElementById(id)!;

function el(tag: string, className = '', text = ''): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

function meter(value: number, min: number, max: number, className = ''): HTMLElement {
  const bar = el('span', `meter ${className}`);
  const fill = el('span');
  fill.style.width = `${((value - min) / (max - min)) * 100}%`;
  bar.append(fill);
  return bar;
}

const signed = (x: number) => `${x > 0 ? '+' : ''}${x.toFixed(2)}`;

function describe(e: Event): string {
  const p = e.payload;
  switch (e.kind) {
    case 'task': return `task ${e.actors[0]} ${p.change ?? ''}`;
    case 'rejected': return `${e.actors[0]} rejected: ${p.reason ?? ''}`;
    case 'outcome':
      return `${p.a} → ${p.b} relation ${signed(Number(p.relation_delta ?? 0))}${p.grievance ? ` · ${p.grievance}` : ''}`;
    case 'session':
      return `${e.actors[0]} ${p.start ? 'opened' : 'closed'} ${p.kind ?? 'session'}` +
        (Array.isArray(p.participants) ? ` (${p.participants.join(', ')})` : '');
    default: return e.text;
  }
}

/** HTML panels over the Phaser canvas: controls, task board, inspect panel, event timeline. */
export class Hud {
  selected: string | null = null;
  private dirty = false;
  private inspected = -1;

  constructor(private world: World, private send: (control: Control) => void, onClose: () => void) {
    $('pause').onclick = () => send({ type: 'control', cmd: this.world.status?.state === 'paused' ? 'resume' : 'pause' });
    $('step').onclick = () => send({ type: 'control', cmd: 'step' });
    const speed = $('speed') as HTMLSelectElement;
    speed.onchange = () => send({ type: 'control', cmd: 'speed', value: Number(speed.value) });
    $('inspect-close').onclick = onClose;
  }

  link(link: Link) {
    $('link').textContent = link;
    $('link').dataset.link = link;
  }

  select(agent: string | null) {
    this.selected = agent;
    this.inspected = -1;
    this.changed();
  }

  /** Coalesces a burst of messages (history replay) into one repaint. */
  changed() {
    if (this.dirty) return;
    this.dirty = true;
    requestAnimationFrame(() => {
      this.dirty = false;
      this.render();
    });
  }

  private render() {
    const { hello, frame, status } = this.world;
    $('run').textContent = hello ? hello.run_id : '—';
    $('clock').textContent = frame && hello
      ? `Day ${frame.day + 1} · tick ${frame.tick % hello.config.ticks_per_day + 1}/${hello.config.ticks_per_day} · ${frame.phase}`
      : 'waiting for first tick';
    $('state').textContent = status?.state ?? 'connecting';
    $('state').dataset.state = status?.state ?? '';
    $('pause').textContent = status?.state === 'paused' ? 'Resume' : 'Pause';
    $('error').textContent = this.world.error ?? '';
    this.renderTasks();
    this.renderInspect();
    this.renderTimeline();
  }

  private renderTasks() {
    const now = this.world.frame?.tick ?? 0;
    const rows = [...this.world.tasks.values()].map(t => {
      const row = el('li', `card ${t.status}${t.status !== 'done' && now > t.due ? ' overdue' : ''}`);
      const head = el('div', 'task-head');
      head.append(el('b', '', t.id), el('span', 'owner', t.owner ?? 'unassigned'), el('span', 'status', t.status));
      const foot = el('div', 'task-foot');
      foot.append(meter(t.progress, 0, 1), el('span', '', `due ${t.due}`));
      row.append(head, el('div', 'title', t.title), foot);
      if (t.blocked_by.length) row.append(el('div', 'blocked', `blocked by ${t.blocked_by.join(', ')}`));
      return row;
    });
    $('tasks').replaceChildren(...rows);
  }

  private renderInspect() {
    const panel = $('inspect-panel');
    panel.hidden = this.selected === null;
    if (this.selected === null) return;
    // The server answers inspect privately; ask again whenever a new tick lands.
    const tick = this.world.frame?.tick ?? -1;
    if (tick !== this.inspected) {
      this.inspected = tick;
      this.send({ type: 'control', cmd: 'inspect', agent: this.selected });
    }
    $('inspect-name').textContent = this.selected;
    const data = this.world.inspect.get(this.selected);
    const body = $('inspect-body');
    if (!data) {
      body.replaceChildren(el('p', 'muted', 'loading…'));
      return;
    }
    const state = el('div', 'state');
    state.append(
      el('span', '', 'stress'), meter(data.state.stress, 0, 1, 'stress'), el('span', 'num', data.state.stress.toFixed(2)),
      el('span', '', 'mood'), meter(data.state.mood, -1, 1, 'mood'), el('span', 'num', signed(data.state.mood)),
    );
    const relations = el('ul', 'relations');
    for (const r of [...data.relationships].sort((x, y) => x.relation - y.relation)) {
      const li = el('li');
      li.append(el('b', '', r.to), meter(r.relation, -1, 1, r.relation < 0 ? 'neg' : 'pos'), el('span', 'num', signed(r.relation)));
      if (r.summary) li.append(el('p', 'summary', r.summary));
      relations.append(li);
    }
    const reflection = el('ul', 'reflection');
    for (const line of data.reflection) reflection.append(el('li', '', line));
    body.replaceChildren(
      el('p', 'muted', `as of tick ${data.tick} · ${data.retrieved.length} memories retrieved`),
      state, el('h3', '', 'Relationships'), relations, el('h3', '', 'Reflection'),
      data.reflection.length ? reflection : el('p', 'muted', 'none yet'),
    );
  }

  private renderTimeline() {
    const rows = this.world.events.slice(-200).reverse().map(e => {
      const row = el('li', `event ${e.kind}`);
      row.append(el('span', 'tick', `t${e.tick}`), el('span', 'kind', e.kind), el('span', '', describe(e)));
      return row;
    });
    $('timeline').replaceChildren(...rows);
  }
}
