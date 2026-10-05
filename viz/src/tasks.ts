import type { Task, TaskRecord } from './messages';
import type { World } from './world';

/** The Tasks tab (tasks by project, each with the evidence on file) and the dependency graph. */

const CORE = 'Core release';
const FILTERS = ['all', 'open', 'review', 'blocked', 'overdue', 'done', 'docs'] as const;
type Filter = (typeof FILTERS)[number];

function el(tag: string, className = '', text = ''): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

function svg(tag: string, attrs: Record<string, string | number> = {}, text = ''): SVGElement {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  node.textContent = text;
  return node;
}

function bar(value: number): HTMLElement {
  const meter = el('span', 'meter');
  const fill = el('span');
  fill.style.width = `${Math.max(0, Math.min(1, value)) * 100}%`;
  meter.append(fill);
  return meter;
}

const project = (t: Task) => t.group ?? CORE;
/** "P10 partner program" sorts after "P9 …"; the core release comes first. */
function projectOrder(a: string, b: string): number {
  if (a === CORE || b === CORE) return a === CORE ? (b === CORE ? 0 : -1) : 1;
  const n = (s: string) => Number(s.match(/^P(\d+)/)?.[1] ?? 1e9);
  return n(a) - n(b) || a.localeCompare(b);
}

/** One word for where a task stands, the colour key everywhere below. */
function state(t: Task, now: number, inReview = false): string {
  if (t.status === 'done') return 'done';
  if ((t.lifecycle ?? t.status) === 'review' || inReview) return 'review';
  if (now > t.due || t.status === 'overdue') return 'overdue';
  if (t.status === 'blocked' || t.blocked_by.length) return 'blocked';
  if (t.progress > 0 || t.lifecycle === 'in_progress') return 'active';
  return t.owner ? 'ready' : 'unassigned';
}

function matches(filter: Filter, s: string, hasDoc: boolean): boolean {
  switch (filter) {
    case 'all': return true;
    case 'open': return s !== 'done';
    case 'docs': return hasDoc;
    default: return s === filter;
  }
}

export class TaskViews {
  private filter: Filter = 'open';
  private open = new Set<string>(); // expanded projects
  private touched = new Set<string>(); // projects the viewer opened or closed by hand
  private task: string | null = null; // the task whose evidence is shown
  private graphTask: string | null = null;
  graphOpen = false;
  private rebuiltAt: { tick: number; records: Map<string, TaskRecord> } | null = null;

  constructor(private world: World, private repaint: () => void) {}

  /** Open one task's evidence, on the board and in the graph. */
  show(id: string) {
    this.task = this.graphTask = id;
    this.filter = 'all';
  }

  /** "written" when the task's document is on file, "pending" when one is expected, else null. */
  private docStatus(t: Task): 'written' | 'pending' | null {
    if ((t.record ?? this.rebuilt(t))?.document) return 'written';
    return t.deliverable ? 'pending' : null;
  }

  /** Older recordings fold review into "overdue"; their rebuilt record still shows it. */
  private state(t: Task): string {
    let inReview = false;
    if (t.lifecycle === undefined && t.status !== 'done') {
      const r = this.rebuilt(t);
      const back = Math.max(-1, ...(r?.rejections.map(x => x.tick) ?? []));
      inReview = r !== null && r.review_tick !== null && r.done_tick === null && r.review_tick > back;
    }
    return state(t, this.now, inReview);
  }

  private get now() { return this.world.frame?.tick ?? 0; }

  private projects(): Map<string, Task[]> {
    const groups = new Map<string, Task[]>();
    for (const t of this.world.tasks.values()) groups.set(project(t), [...(groups.get(project(t)) ?? []), t]);
    return new Map([...groups].sort(([a], [b]) => projectOrder(a, b)));
  }

  // ---- Tasks tab ----

  renderBoard(box: HTMLElement) {
    const now = this.now;
    const all = [...this.world.tasks.values()];
    const states = new Map(all.map(t => [t.id, this.state(t)]));
    const count = (s: string) => all.filter(t => states.get(t.id) === s).length;
    const docs = new Set(all.filter(t => this.docStatus(t)).map(t => t.id));

    const top = el('div', 'board-top');
    const total = el('div', 'board-total');
    const done = count('done');
    total.append(el('b', '', `${done}/${all.length}`), el('span', 'muted', 'done'), bar(all.length ? done / all.length : 0));
    const graph = el('button', 'primary', 'Dependency graph');
    graph.onclick = () => { this.graphOpen = true; this.repaint(); };
    top.append(total, graph);

    const filters = el('div', 'filters');
    for (const f of FILTERS) {
      const n = f === 'all' ? all.length : f === 'open' ? all.length - done : f === 'docs' ? docs.size : count(f);
      const chip = el('button', `filter ${f}${f === this.filter ? ' on' : ''}`, `${f} ${n}`);
      chip.onclick = () => { this.filter = f; this.repaint(); };
      filters.append(chip);
    }

    const sections: HTMLElement[] = [];
    for (const [name, tasks] of this.projects()) {
      const shown = tasks.filter(t => matches(this.filter, states.get(t.id)!, docs.has(t.id)));
      if (!shown.length) continue;
      const finished = tasks.filter(t => t.status === 'done').length;
      const late = tasks.some(t => states.get(t.id) === 'overdue');
      // Unless the viewer chose, a project is open while it has something the filter shows
      // that is not done, and the core release always starts open.
      const isOpen = this.touched.has(name) ? this.open.has(name) : name === CORE || shown.some(t => t.status !== 'done');
      const section = el('section', `project${isOpen ? ' open' : ''}${late ? ' late' : ''}`);
      const head = el('button', 'project-head');
      const label = el('span', 'project-name');
      const [code, ...rest] = name === CORE ? ['Core', 'release'] : name.split(' ');
      label.append(el('b', '', code), document.createTextNode(` ${rest.join(' ')}`));
      head.append(el('span', 'caret', isOpen ? '▾' : '▸'), label, bar(finished / tasks.length),
        el('span', 'project-count', `${finished}/${tasks.length}`));
      head.onclick = () => {
        this.touched.add(name);
        if (isOpen) this.open.delete(name); else this.open.add(name);
        this.repaint();
      };
      section.append(head);
      if (isOpen) {
        const list = el('ul', 'task-list');
        for (const t of shown) list.append(this.row(t, states.get(t.id)!));
        section.append(list);
      }
      sections.push(section);
    }
    if (!sections.length) sections.push(el('p', 'muted empty', 'No task matches this filter.'));
    box.replaceChildren(top, filters, ...sections);
  }

  private row(t: Task, s: string): HTMLElement {
    const li = el('li', `task-row ${s}${this.task === t.id ? ' open' : ''}`);
    const line = el('button', 'task-line');
    line.append(el('span', `dot ${s}`), el('b', 'task-id', t.id.replace(/^P\d+-/, '')), el('span', 'task-title', t.title));
    if (t.cross) line.append(el('span', 'tag cross', 'cross'));
    const doc = this.docStatus(t);
    if (doc) line.append(el('span', `tag doc ${doc}`, 'doc'));
    line.append(el('span', 'task-owner', t.owner?.replace(/^HDS-/, '#') ?? '—'), bar(t.progress), el('span', 'task-due', `d${t.due}`));
    line.title = `${t.id} · ${t.title} · ${t.owner ?? 'unassigned'} · ${s}`;
    line.onclick = () => { this.task = this.task === t.id ? null : t.id; this.repaint(); };
    li.append(line);
    if (this.task === t.id) li.append(this.detail(t, s, id => { this.task = id; this.repaint(); }));
    return li;
  }

  /** The evidence on file for one task; `go` follows a prerequisite. */
  private detail(t: Task, s: string, go: (id: string) => void): HTMLElement {
    const box = el('div', 'evidence');
    const facts = el('dl', 'facts');
    const fact = (k: string, v: string | HTMLElement) => {
      facts.append(el('dt', '', k));
      const dd = el('dd');
      dd.append(v);
      facts.append(dd);
    };
    fact('task', `${t.id} · ${t.title}`);
    fact('project', `${project(t)}${t.cross ? ' (cross step for another department)' : ''}`);
    fact('state', `${s} · ${Math.round(t.progress * 100)}% · due tick ${t.due}`);
    const deps = [...(this.world.deps.get(t.id) ?? [])];
    if (deps.length) {
      const chips = el('span', 'dep-chips');
      for (const d of deps) {
        const dep = this.world.tasks.get(d);
        const chip = el('button', `dep ${dep ? this.state(dep) : ''}`, d);
        chip.onclick = () => go(d);
        chips.append(chip);
      }
      fact('needs', chips);
    }
    const r = t.record ?? this.rebuilt(t);
    if (!r) {
      box.append(facts, el('p', 'muted', 'No evidence: this recording has neither task records nor an events.jsonl.'));
      return box;
    }
    fact('owner', r.owner ?? 'unassigned');
    const worked = Object.entries(r.worked_by).map(([who, n]) => `${who} ×${n}`).join(', ');
    fact('worked', worked || 'nobody yet');
    const times = [
      r.started_tick !== null ? `started t${r.started_tick}` : 'not started',
      r.review_tick !== null ? `review t${r.review_tick}` : '',
      r.done_tick !== null ? `done t${r.done_tick} (${r.on_time ? 'on time' : 'late'})` : '',
    ].filter(Boolean).join(' → ');
    fact('timeline', times);
    if (r.approved_by) fact('approved', `${r.approved_by}${r.approval_note ? ` — “${r.approval_note}”` : ''}`);
    if (r.handoff_to.length) fact('hands to', r.handoff_to.join(', '));
    box.append(facts);
    if (r.rejections.length) {
      box.append(el('h4', '', `Returned ${r.rejections.length}×`));
      const list = el('ul', 'rejections');
      for (const x of r.rejections) list.append(el('li', '', `t${x.tick} ${x.by}: ${x.note ?? '(no note)'}`));
      box.append(list);
    }
    if (r.document || t.deliverable) {
      const doc = el('section', 'document');
      doc.append(el('h4', '', 'Document'));
      if (t.deliverable) doc.append(el('p', 'expected', `Form: ${t.deliverable}`));
      if (t.criteria) doc.append(el('p', 'expected', `Review checks: ${t.criteria}`));
      doc.append(r.document ? el('pre', '', r.document) : el('p', 'muted', 'not written yet'));
      box.append(doc);
    }
    box.append(el('h4', '', 'Owner’s summary'), el('p', r.summary ? 'summary' : 'muted', r.summary ?? 'none yet'));
    return box;
  }

  /** The record as it stood at the tick on screen, rebuilt from `events.jsonl` for recordings made
   * before frames carried it: accepted work, review/approved/revision changes and summaries. */
  private rebuilt(t: Task): TaskRecord | null {
    const events = this.world.engineEvents;
    if (!events.length) return null;
    const now = this.now;
    if (this.rebuiltAt?.tick !== now) {
      const records = new Map<string, TaskRecord>();
      const rec = (id: string) => {
        if (!records.has(id)) records.set(id, rec0());
        return records.get(id)!;
      };
      // A refused action is followed, the same tick, by a `rejected` event for its actor.
      const refused = new Set(events.filter(e => e.kind === 'rejected').map(e => `${e.tick}\t${e.actor}`));
      const verdicts = new Map<string, { by: string | null; note: string | null }>(); // latest approve/reject per task
      for (const e of events) {
        if (e.tick > now) break;
        const p = e.payload;
        if (e.kind === 'action' && typeof p.task === 'string' && !refused.has(`${e.tick}\t${e.actor}`)) {
          if (p.kind === 'work') {
            const r = rec(p.task);
            r.worked_by[e.actor!] = (r.worked_by[e.actor!] ?? 0) + 1;
            r.started_tick ??= e.tick;
          } else if (p.kind === 'approve' || p.kind === 'reject') {
            verdicts.set(p.task, { by: e.actor, note: (p.text as string | null) ?? null });
          }
        } else if (e.kind === 'task' && e.actor) {
          const r = rec(e.actor);
          const verdict = verdicts.get(e.actor);
          switch (p.change) {
            case 'review': r.review_tick = e.tick; break;
            case 'done': r.done_tick = e.tick; break;
            case 'approved':
              r.done_tick = e.tick;
              r.approved_by = verdict?.by ?? null;
              r.approval_note = verdict?.note ?? null;
              break;
            case 'revision': r.rejections.push({ by: verdict?.by ?? '?', tick: e.tick, note: verdict?.note ?? null }); break;
            case 'summary':
              r.summary = (p.summary as string) ?? null;
              r.document = (p.document as string | undefined) ?? r.document;
              break;
          }
        }
      }
      this.rebuiltAt = { tick: now, records };
    }
    const r = { ...(this.rebuiltAt.records.get(t.id) ?? rec0()) };
    r.owner = t.owner;
    r.team = Object.keys(r.worked_by);
    r.due = t.due;
    r.on_time = r.done_tick !== null && r.done_tick <= t.due;
    return r;
  }

  // ---- Dependency graph overlay ----

  renderGraph(box: HTMLElement) {
    box.hidden = !this.graphOpen;
    if (!this.graphOpen) return;
    const now = this.now;
    const tasks = [...this.world.tasks.values()];
    const byId = new Map(tasks.map(t => [t.id, t]));
    const deps = (id: string) => [...(this.world.deps.get(id) ?? [])].filter(d => byId.has(d));

    // Column = longest chain of prerequisites before it; lane = its project.
    const depth = new Map<string, number>();
    const depthOf = (id: string, seen = new Set<string>()): number => {
      if (depth.has(id)) return depth.get(id)!;
      if (seen.has(id)) return 0; // a cycle would be a config error; do not hang on it
      seen.add(id);
      const d = Math.max(-1, ...deps(id).map(p => depthOf(p, seen))) + 1;
      depth.set(id, d);
      return d;
    };
    tasks.forEach(t => depthOf(t.id));

    const [colW, nodeW, nodeH, rowH, laneGap, laneLabel, pad] = [168, 140, 42, 52, 14, 150, 16];
    const pos = new Map<string, { x: number; y: number }>();
    const lanes: { name: string; y: number; h: number; done: number; total: number }[] = [];
    let y = pad;
    for (const [name, group] of this.projects()) {
      const columns = new Map<number, Task[]>();
      for (const t of group) columns.set(depth.get(t.id)!, [...(columns.get(depth.get(t.id)!) ?? []), t]);
      const rows = Math.max(...[...columns.values()].map(c => c.length));
      for (const [d, column] of columns) {
        column.forEach((t, i) => pos.set(t.id, { x: laneLabel + pad + d * colW, y: y + 8 + i * rowH }));
      }
      const h = rows * rowH + 8;
      lanes.push({ name, y, h, done: group.filter(t => t.status === 'done').length, total: group.length });
      y += h + laneGap;
    }
    const width = laneLabel + pad * 2 + (Math.max(0, ...depth.values()) + 1) * colW;
    const height = y + pad;

    const focus = this.graphTask;
    const near = new Set<string>(focus ? [focus, ...deps(focus), ...tasks.filter(t => deps(t.id).includes(focus)).map(t => t.id)] : []);
    const root = svg('svg', { width, height, viewBox: `0 0 ${width} ${height}`, class: 'dag' });
    const defs = svg('defs');
    const marker = svg('marker', { id: 'dag-arrow', viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: 'auto' });
    marker.append(svg('path', { d: 'M0,0 L10,5 L0,10 z', class: 'arrow' }));
    defs.append(marker);
    root.append(defs);
    for (const lane of lanes) {
      root.append(svg('rect', { x: 4, y: lane.y, width: width - 8, height: lane.h, rx: 12, class: 'lane' }));
      const [code, ...rest] = lane.name === CORE ? ['Core', 'release'] : lane.name.split(' ');
      root.append(svg('text', { x: 18, y: lane.y + 22, class: 'lane-code' }, code));
      root.append(svg('text', { x: 18, y: lane.y + 38, class: 'lane-name' }, rest.join(' ')));
      root.append(svg('rect', { x: 18, y: lane.y + 48, width: 110, height: 5, rx: 2.5, class: 'lane-track' }));
      root.append(svg('rect', { x: 18, y: lane.y + 48, width: (110 * lane.done) / lane.total, height: 5, rx: 2.5, class: 'lane-fill' }));
      root.append(svg('text', { x: 134, y: lane.y + 53, class: 'lane-count' }, `${lane.done}/${lane.total}`));
    }
    for (const t of tasks) {
      const to = pos.get(t.id)!;
      for (const d of deps(t.id)) {
        const from = pos.get(d)!;
        const [sx, sy, ex, ey] = [from.x + nodeW, from.y + nodeH / 2, to.x - 2, to.y + nodeH / 2];
        const bend = Math.max(30, (ex - sx) / 2);
        const lit = focus !== null && (t.id === focus || d === focus);
        const doneEdge = byId.get(d)!.status === 'done';
        root.append(svg('path', {
          d: `M${sx},${sy} C${sx + bend},${sy} ${ex - bend},${ey} ${ex},${ey}`,
          class: `edge${doneEdge ? ' met' : ''}${lit ? ' lit' : ''}${focus && !lit ? ' faded' : ''}`,
          'marker-end': 'url(#dag-arrow)',
        }));
      }
    }
    for (const t of tasks) {
      const { x, y: ny } = pos.get(t.id)!;
      const s = this.state(t);
      const g = svg('g', { class: `node ${s}${t.cross ? ' cross' : ''}${t.id === focus ? ' focus' : ''}${focus && !near.has(t.id) ? ' faded' : ''}` });
      g.append(svg('rect', { x, y: ny, width: nodeW, height: nodeH, rx: 9, class: 'box' }));
      g.append(svg('rect', { x: x + 1, y: ny + nodeH - 5, width: (nodeW - 2) * t.progress, height: 4, rx: 2, class: 'progress' }));
      g.append(svg('text', { x: x + 9, y: ny + 16, class: 'id' }, t.id.replace(/^P\d+-/, '')));
      g.append(svg('text', { x: x + nodeW - 8, y: ny + 16, class: 'owner' }, t.owner?.replace(/^HDS-/, '#') ?? '—'));
      const title = t.title.length > 24 ? `${t.title.slice(0, 23)}…` : t.title;
      g.append(svg('text', { x: x + 9, y: ny + 31, class: 'title' }, title));
      g.append(svg('title', {}, `${t.id} · ${t.title}\n${s} · ${Math.round(t.progress * 100)}% · due ${t.due} · ${t.owner ?? 'unassigned'}`));
      g.addEventListener('click', () => { this.graphTask = this.graphTask === t.id ? null : t.id; this.repaint(); });
      root.append(g);
    }

    const all = tasks.length, done = tasks.filter(t => t.status === 'done').length;
    const head = el('div', 'graph-head');
    const title = el('div', 'graph-title');
    title.append(el('h2', '', 'Dependencies'), el('span', 'muted', `tick ${now} · ${done}/${all} done`), bar(all ? done / all : 0));
    const legend = el('div', 'graph-legend');
    for (const s of ['done', 'active', 'review', 'ready', 'blocked', 'overdue']) {
      const item = el('span', 'legend-item');
      item.append(el('span', `dot ${s}`), document.createTextNode(s));
      legend.append(item);
    }
    legend.append(el('span', 'legend-item muted', 'dashed = cross step · click a task for its evidence'));
    const close = el('button', 'icon', '×');
    close.title = 'close';
    close.onclick = () => { this.graphOpen = false; this.repaint(); };
    head.append(title, legend, close);

    const canvas = el('div', 'graph-canvas');
    const keep = box.querySelector('.graph-canvas');
    canvas.append(root);
    const side = el('aside', 'graph-detail');
    const picked = focus ? byId.get(focus) : undefined;
    if (picked) side.append(this.detail(picked, this.state(picked), id => { this.graphTask = id; this.repaint(); }));
    else side.append(el('p', 'muted', 'Select a task to see its evidence and highlight what it waits on and what waits on it.'));
    const body = el('div', 'graph-body');
    body.append(canvas, side);
    // Keep the scroll position across repaints (a frame lands every tick).
    const [left, top] = keep ? [keep.scrollLeft, keep.scrollTop] : [0, 0];
    box.replaceChildren(head, body);
    canvas.scrollLeft = left;
    canvas.scrollTop = top;
  }
}

function rec0(): TaskRecord {
  return {
    owner: null, team: [], worked_by: {}, started_tick: null, review_tick: null, done_tick: null,
    due: 0, on_time: false, approved_by: null, approval_note: null, rejections: [],
    summary: null, document: null, prerequisites: [], handoff_to: [],
  };
}
