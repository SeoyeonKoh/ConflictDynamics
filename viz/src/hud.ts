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

function svg(tag: string, attrs: Record<string, string | number> = {}, text = ''): SVGElement {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  node.textContent = text;
  return node;
}

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

  constructor(
    private world: World,
    private send: (control: Control) => void,
    private choose: (agent: string | null) => void,
  ) {
    $('pause').onclick = () => send({ type: 'control', cmd: this.world.status?.state === 'paused' ? 'resume' : 'pause' });
    $('step').onclick = () => send({ type: 'control', cmd: 'step' });
    const speed = $('speed') as HTMLSelectElement;
    speed.onchange = () => send({ type: 'control', cmd: 'speed', value: Number(speed.value) });
    $('inspect-close').onclick = () => choose(null);
    for (const tab of document.querySelectorAll<HTMLButtonElement>('.tabs button')) {
      tab.onclick = () => {
        for (const other of document.querySelectorAll<HTMLButtonElement>('.tabs button')) {
          other.classList.toggle('on', other === tab);
          $(other.dataset.tab!).hidden = other !== tab;
        }
        this.changed();
      };
    }
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
    this.renderRelations();
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

  /** Directed relations rebuilt from outcome events (they reproduce the engine's values exactly:
   * each `relation_delta` is added and clamped to [-1, 1]), so any tick, live or replayed, works. */
  private renderRelations() {
    const box = $('relations');
    if (box.hidden) return;
    const names = this.world.hello?.agents.map(a => a.id) ?? [];
    const relation = new Map<string, number>();
    for (const e of this.world.events) {
      if (e.kind !== 'outcome') continue;
      const key = `${e.payload.a}\t${e.payload.b}`;
      const value = (relation.get(key) ?? 0) + Number(e.payload.relation_delta ?? 0);
      relation.set(key, Math.max(-1, Math.min(1, value)));
    }
    const [w, h, r, node] = [300, 270, 105, 17];
    const at = new Map(names.map((name, i) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * i) / names.length;
      return [name, { x: w / 2 + r * Math.cos(angle), y: h / 2 + r * Math.sin(angle) }];
    }));
    const root = svg('svg', { viewBox: `0 0 ${w} ${h}` });
    const defs = svg('defs');
    for (const [id, colour] of [['pos', '#7ee787'], ['neg', '#ff7b72']]) {
      const marker = svg('marker', { id, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 5, markerHeight: 5, orient: 'auto' });
      marker.append(svg('path', { d: 'M0,0 L10,5 L0,10 z', fill: colour }));
      defs.append(marker);
    }
    root.append(defs);
    for (const [key, value] of relation) {
      const [a, b] = key.split('\t').map(n => at.get(n));
      if (!a || !b || Math.abs(value) < 0.02) continue;
      // Each direction bends to its own side, so A→B and B→A stay apart.
      const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy);
      const [ux, uy] = [dx / len, dy / len];
      const cx = (a.x + b.x) / 2 - uy * 22, cy = (a.y + b.y) / 2 + ux * 22;
      const [sx, sy] = [a.x + ux * node, a.y + uy * node], [ex, ey] = [b.x - ux * (node + 2), b.y - uy * (node + 2)];
      const kind = value < 0 ? 'neg' : 'pos';
      const edge = svg('path', {
        d: `M${sx},${sy} Q${cx},${cy} ${ex},${ey}`, fill: 'none', stroke: kind === 'neg' ? '#ff7b72' : '#7ee787',
        'stroke-width': 1 + 3 * Math.abs(value), opacity: 0.35 + 0.65 * Math.abs(value), 'marker-end': `url(#${kind})`,
      });
      const [from, to] = key.split('\t');
      edge.append(svg('title', {}, `${from} → ${to} ${signed(value)}`));
      root.append(edge, svg('text', { x: cx, y: cy, class: 'value' }, signed(value)));
    }
    for (const name of names) {
      const { x, y } = at.get(name)!;
      const g = svg('g', { class: `node${name === this.selected ? ' selected' : ''}` });
      g.append(svg('circle', { cx: x, cy: y, r: node }), svg('text', { x, y }, name.slice(0, 7)));
      g.addEventListener('click', () => this.choose(name));
      root.append(g);
    }
    const legend = el('p', 'legend', 'A → B: how A sees B · green +, red −, thicker = stronger · click a person to inspect');
    box.replaceChildren(root, legend);
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
      el('span', '', 'mood'), meter(data.state.mood, -1, 1, data.state.mood < 0 ? 'neg' : 'pos'), el('span', 'num', signed(data.state.mood)),
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
    // Events and utterances by tick; within a tick, openings come before what was said in them.
    const rank = (e: Event) => (e.kind === 'session' && e.payload.start ? 0 : 2);
    const items = [
      ...this.world.events.map((e, i) => ({ tick: e.tick, rank: rank(e), i, kind: e.kind, text: describe(e) })),
      ...this.world.lines.map((l, i) => ({
        tick: l.tick, rank: 1, i, kind: l.session.startsWith('dm:') ? '✉ says' : 'says', text: `${l.speaker}: ${l.text}`,
      })),
    ].sort((x, y) => x.tick - y.tick || x.rank - y.rank || x.i - y.i);
    const rows = items.slice(-200).reverse().map(item => {
      const row = el('li', `event ${item.kind === 'says' || item.kind === '✉ says' ? 'line' : item.kind}`);
      row.append(el('span', 'tick', `t${item.tick}`), el('span', 'kind', item.kind), el('span', '', item.text));
      return row;
    });
    $('timeline').replaceChildren(...rows);
  }
}
