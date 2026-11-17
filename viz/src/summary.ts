// A run's results at a glance (summary.html): task progress, why agents sat idle, stress and
// relationships, from `GET /api/runs/<run>/summary` (src/conflict_sim/run_summary.py).
// `?run=<dir under runs/>` names the run; `&live=<id>` marks one conflict-server is running, which
// refreshes while it runs and links back to the live view.
import { t, type Key } from './i18n';
import { applyTheme, getLang } from './prefs';
import { ApiError, ICONS, api, h, langSwitch, navPill } from './ui';

interface Stats { n: number; mean: number | null; std: number | null; min: number | null; max: number | null }
type IdleKind = 'no_workable' | 'waiting_approval' | 'other_idle';
interface Summary {
  run: string; scenario: string | null; status: string; tick: number; day: number; day_span: number;
  agents: { id: string; name: string }[];
  tasks: {
    total: number; done: number; started: number; done_before_start: number; completion_pct: number;
    mean_progress_pct: number; by_status: Record<string, number>; on_time: number; late: number; overdue_open: number;
  };
  idle: {
    work_ticks: number; idle_ticks: number; idle_pct: number; counts: Record<IdleKind, number>;
    pct_of_work: Record<IdleKind, number>; share_of_idle: Record<IdleKind, number>;
    per_agent: Record<string, Record<IdleKind, number> & { work_ticks: number }>;
  };
  stress: Stats & {
    agents: { agent: string; stress: number }[];
    timeline: { tick: number; day: number; mean: number; min: number; max: number }[];
    daily: { day: number; mean: number }[];
  };
  relations: Stats & {
    edges: number; pairs: number; negative_edges: number; negative_pairs: number; conflict_threshold: number; conflict_pairs: number;
    mutual_negative_pairs: number; grievances: number;
    histogram: { from: number; to: number; n: number }[];
    changes: { from: string; to: string; start: number; now: number; delta: number }[];
  };
}

const REFRESH_S = 5;
const IDLE: [IdleKind, Key, Key][] = [
  ['no_workable', 'idleNoWorkable', 'idleNoWorkableDesc'],
  ['waiting_approval', 'idleWaiting', 'idleWaitingDesc'],
  ['other_idle', 'idleOther', 'idleOtherDesc'],
];
const STATUS: [string, Key][] = [
  ['done', 'stDone'], ['review', 'stReview'], ['in_progress', 'stInProgress'], ['ready', 'stReady'],
  ['blocked', 'stBlocked'], ['overdue', 'stOverdue'], ['unassigned', 'stUnassigned'],
];

const params = new URLSearchParams(location.search);
const run = params.get('run');
let liveId = params.get('live');
applyTheme();

const num = (v: number | null, digits = 2) => (v === null ? '–' : v.toFixed(digits));
const pct = (v: number) => `${v.toFixed(v > 0 && v < 10 ? 1 : 0)}%`;
const signed = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)}`;
const clock = (tick: number, span: number) => {
  const minutes = 9 * 60 + 15 * (tick % span);
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
};

function card(title: Key, ...children: (Node | null)[]) {
  return h('section', { class: 'sm-card' }, h('h2', {}, t(title)), ...children);
}
function stat(label: string, value: string, cls = '') {
  return h('div', { class: `sm-stat ${cls}` }, h('b', {}, value), h('span', {}, label));
}
/** One bar made of coloured parts, each `n` wide out of their sum. */
function stack(parts: { n: number; cls: string; label: string }[]) {
  const total = parts.reduce((s, p) => s + p.n, 0);
  const bar = h('div', { class: 'sm-stack' });
  for (const p of parts) {
    if (!p.n) continue;
    bar.append(h('span', { class: p.cls, style: `flex:${p.n}`, title: `${p.label} ${p.n}` }));
  }
  if (!total) bar.append(h('span', { class: 'empty', style: 'flex:1' }));
  return bar;
}
function legend(parts: { n: number; cls: string; label: string; note?: string }[]) {
  return h('ul', { class: 'sm-legend' }, ...parts.map(p => h('li', {},
    h('i', { class: p.cls }), h('span', {}, p.label), h('b', {}, String(p.n)), p.note ? h('small', {}, p.note) : null)));
}

function tasksCard(s: Summary) {
  const k = s.tasks;
  const known = new Set(STATUS.map(([st]) => st));
  const parts = [...STATUS.map(([st, key]) => ({ n: k.by_status[st] ?? 0, cls: `st-${st}`, label: t(key) })),
    ...Object.entries(k.by_status).filter(([st]) => !known.has(st)).map(([st, n]) => ({ n, cls: 'st-other', label: st }))];
  const deadline = [{ n: k.on_time, cls: 'ok', label: t('smOnTime') }, { n: k.late, cls: 'bad', label: t('smLate') }];
  const notes = [k.overdue_open ? t('smOverdueOpen', { n: k.overdue_open }) : '',
    k.done_before_start ? t('smBeforeStart', { n: k.done_before_start }) : ''].filter(Boolean).join(' · ');
  return card('smTasks',
    h('div', { class: 'sm-stats' }, stat(t('smCompletion'), pct(k.completion_pct), 'big'),
      stat(t('smDone'), `${k.done}/${k.total}`), stat(t('smStarted'), String(k.started)),
      stat(t('smMeanProgress'), pct(k.mean_progress_pct))),
    h('h3', {}, t('smByStatus')), stack(parts), legend(parts.filter(p => p.n)),
    h('h3', {}, t('smDeadline')), stack(deadline), legend(deadline),
    notes ? h('p', { class: 'sm-note' }, notes) : null);
}

function idleCard(s: Summary, names: Map<string, string>) {
  const k = s.idle;
  const parts = IDLE.map(([kind, label, desc]) => ({ kind, n: k.counts[kind], cls: `idle-${kind}`, label: t(label),
    note: `${pct(k.pct_of_work[kind])} · ${t('smShareOfIdle', { pct: pct(k.share_of_idle[kind]) })}`, desc: t(desc) }));
  const rows = Object.entries(k.per_agent).map(([agent, c]) => {
    const total = IDLE.reduce((sum, [kind]) => sum + c[kind], 0);
    const bar = h('div', { class: 'sm-stack thin' });
    for (const [kind, label] of IDLE) {
      if (c[kind]) bar.append(h('span', { class: `idle-${kind}`, style: `width:${(100 * c[kind]) / Math.max(c.work_ticks, 1)}%`, title: `${t(label)} ${c[kind]}` }));
    }
    return h('div', { class: 'sm-row' }, h('span', { class: 'who', title: agent }, names.get(agent) ?? agent), bar,
      h('span', { class: 'num' }, `${total}/${c.work_ticks}`));
  });
  return card('smIdle', h('p', { class: 'sm-note' }, t('smIdleRule')),
    h('div', { class: 'sm-stats' }, stat(t('smIdleTotal'), pct(k.idle_pct), 'big'),
      ...parts.map(p => stat(p.label, pct(k.pct_of_work[p.kind]), `tone-${p.kind}`))),
    h('p', { class: 'sm-note' }, t('smWorkTicks', { n: k.work_ticks, idle: k.idle_ticks })), stack(parts),
    h('ul', { class: 'sm-legend' }, ...parts.map(p => h('li', { title: p.desc }, h('i', { class: p.cls }),
      h('span', {}, p.label), h('b', {}, String(p.n)), h('small', {}, p.note), h('em', {}, p.desc)))),
    h('h3', {}, t('smPerAgent')), h('div', { class: 'sm-rows' }, ...rows));
}

const SVG = 'http://www.w3.org/2000/svg';
function svg<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number> = {}, ...kids: Node[]) {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
  el.append(...kids);
  return el;
}

/** Mean stress per tick with its min–max band, day boundaries marked. */
function trend(s: Summary) {
  const points = s.stress.timeline;
  if (!points.length) return h('p', { class: 'sm-note' }, t('smEmpty'));
  const W = 640, H = 180, L = 34, R = 8, T = 10, B = 24;
  const last = points[points.length - 1].tick || 1;
  const top = Math.max(0.2, ...points.map(p => p.max));
  const x = (tick: number) => L + ((W - L - R) * tick) / last;
  const y = (v: number) => T + (H - T - B) * (1 - v / top);
  const chart = svg('svg', { viewBox: `0 0 ${W} ${H}`, class: 'sm-chart', role: 'img', 'aria-label': t('smStressTrend') });
  for (const v of [0, top / 2, top]) {
    chart.append(svg('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), class: 'grid' }),
      svg('text', { x: L - 6, y: y(v) + 3, class: 'axis', 'text-anchor': 'end' }, document.createTextNode(v.toFixed(2))));
  }
  for (const d of s.stress.daily) {
    const at = d.day * s.day_span;
    if (at > last) continue;
    // Day 1 starts on the y axis itself: its label only, no second line over the axis.
    if (d.day > 0) chart.append(svg('line', { x1: x(at), x2: x(at), y1: T, y2: H - B, class: 'day' }));
    chart.append(svg('text', { x: x(at) + 3, y: H - 6, class: 'axis' }, document.createTextNode(t('smDay', { n: d.day + 1 }))));
  }
  const band = points.map(p => `${x(p.tick)},${y(p.max)}`).concat([...points].reverse().map(p => `${x(p.tick)},${y(p.min)}`));
  chart.append(svg('polygon', { points: band.join(' '), class: 'band' }),
    svg('polyline', { points: points.map(p => `${x(p.tick)},${y(p.mean)}`).join(' '), class: 'mean' }));
  for (const p of points) {
    chart.append(svg('circle', { cx: x(p.tick), cy: y(p.mean), r: 6, class: 'hit' },
      svg('title', {}, document.createTextNode(`tick ${p.tick} · ${t('smMean')} ${p.mean.toFixed(3)} · ${p.min.toFixed(2)}–${p.max.toFixed(2)}`))));
  }
  return chart;
}

function stressCard(s: Summary, names: Map<string, string>) {
  const k = s.stress;
  const bars = k.agents.map(a => h('div', { class: 'sm-row' },
    h('span', { class: 'who', title: a.agent }, names.get(a.agent) ?? a.agent),
    h('div', { class: 'sm-meter' }, h('span', { class: a.stress >= 0.6 ? 'hot' : a.stress >= 0.3 ? 'warm' : 'cool', style: `width:${Math.min(a.stress, 1) * 100}%` })),
    h('span', { class: 'num' }, a.stress.toFixed(2))));
  return card('smStress',
    h('div', { class: 'sm-stats' }, stat(t('smMean'), num(k.mean), 'big'), stat(t('smStd'), num(k.std)),
      stat(t('smMin'), num(k.min)), stat(t('smMax'), num(k.max))),
    h('h3', {}, t('smStressTrend')), trend(s),
    h('h3', {}, t('smStressByAgent')), h('div', { class: 'sm-rows' }, ...bars));
}

function relationsCard(s: Summary, names: Map<string, string>) {
  const k = s.relations;
  const most = Math.max(1, ...k.histogram.map(b => b.n));
  const histogram = h('div', { class: 'sm-hist' }, ...k.histogram.map(b => h('div', { class: 'col', title: `${b.from} – ${b.to}: ${b.n}` },
    h('b', {}, String(b.n)), h('span', { class: b.n === 0 ? 'zero' : b.to <= 0 ? 'neg' : 'pos', style: `height:${(100 * b.n) / most}%` }),
    h('small', {}, `${b.from}…${b.to}`))));
  const who = (id: string) => names.get(id) ?? id;
  const changes = k.changes.length
    ? h('ul', { class: 'sm-changes' }, ...k.changes.map(c => h('li', {},
      h('span', {}, `${who(c.from)} → ${who(c.to)}`), h('span', { class: 'num' }, `${c.start.toFixed(2)} → ${c.now.toFixed(2)}`),
      h('b', { class: c.delta < 0 ? 'neg' : 'pos' }, signed(c.delta)))))
    : h('p', { class: 'sm-note' }, t('smNoChanges'));
  return card('smRelations', h('p', { class: 'sm-note' }, `${t('smRelationsRule')} ${t('smEdges', { n: k.edges, pairs: k.pairs })}`),
    h('div', { class: 'sm-stats' }, stat(t('smMean'), num(k.mean), 'big'), stat(t('smStd'), num(k.std)),
      stat(t('smMin'), num(k.min)), stat(t('smMax'), num(k.max))),
    h('div', { class: 'sm-stats' }, stat(t('smNegativePairs'), String(k.negative_pairs), 'neg'),
      stat(t('smConflictPairs', { v: k.conflict_threshold }), String(k.conflict_pairs), 'neg'),
      stat(t('smMutualNegative'), String(k.mutual_negative_pairs), 'neg'), stat(t('smGrievances'), String(k.grievances))),
    h('h3', {}, t('smDistribution')), histogram, h('h3', {}, t('smChanges')), changes);
}

const root = document.getElementById('summary-root')!;
let data: Summary | null = null;
let failure: string | null = null;
let stale = false; // a live refresh failed: what shows is the last summary that loaded
let shown = ''; // what the page last drew, so an unchanged refresh keeps hover and scroll as they are

/** A run's folder as a URL path: each segment encoded, the slashes kept. */
const runPath = (r: string) => r.split('/').map(encodeURIComponent).join('/');
const STATE: Record<string, Key> = { running: 'running', completed: 'done', paused: 'paused', failed: 'failed' };

function render() {
  const key = JSON.stringify([data, failure, stale, liveId, getLang()]);
  if (key === shown) return;
  shown = key;
  document.documentElement.lang = getLang();
  const nav = navPill([{ href: '/', icon: ICONS.home, label: t('menu') }, ...(run ? [{
    href: liveId ? `/view.html?live=${encodeURIComponent(liveId)}` : `/view.html?replay=${encodeURIComponent(run)}`,
    icon: liveId ? ICONS.live : ICONS.replay, label: t(liveId ? 'smToLive' : 'smToReplay'),
  }] : [])]);
  const lang = langSwitch(() => render());
  const state = data ? h('span', { class: `sm-state ${data.status}` }, STATE[data.status] ? t(STATE[data.status]) : data.status) : null;
  const head = h('header', { class: 'sm-head' },
    h('div', { class: 'sm-nav' }, nav, h('span', { class: 'spacer' }), lang),
    h('h1', {}, t('smTitle')),
    h('p', { class: 'sm-sub' }, run ?? '', data?.scenario ? ` · ${data.scenario}` : ''),
    data ? h('div', { class: 'sm-meta' }, state, h('span', { class: 'sm-when' }, t('smAsOf', { day: data.day + 1, clock: clock(Math.max(data.tick, 0), data.day_span), tick: data.tick })),
      liveId ? h('span', { class: 'sm-live' }, t(stale ? 'smRetrying' : 'smRefreshing', { s: REFRESH_S })) : null) : null);
  if (failure || !data) {
    root.replaceChildren(h('div', { class: 'sm-page' }, head, h('p', { class: 'sm-note' }, failure ?? t('loading'))));
    return;
  }
  const names = new Map(data.agents.map(a => [a.id, a.name]));
  // Two independent columns, so a long card on one side does not stretch its neighbour.
  root.replaceChildren(h('div', { class: 'sm-page' }, head, h('div', { class: 'sm-grid' },
    h('div', { class: 'sm-col' }, tasksCard(data), stressCard(data, names)),
    h('div', { class: 'sm-col' }, idleCard(data, names), relationsCard(data, names)))));
}

let requested = 0; // numbers each read: only the newest one's answer is drawn
async function load() {
  if (!run) {
    failure = t('smNoRun');
    return render();
  }
  const mine = ++requested;
  try {
    const got = await api<Summary>(`/api/runs/${runPath(run)}/summary`);
    if (mine !== requested) return;
    data = got;
    failure = null;
    stale = false;
  } catch (error) {
    if (mine !== requested) return;
    if (data && liveId) stale = true; // a blip while live: keep the last summary and try again
    else failure = error instanceof ApiError && error.status === 404 ? t('smNoRun') : String(error);
  }
  render();
}

/** While the run is live: read again REFRESH_S after the last read finished (never two at once),
 * not while the tab is hidden. Only `/api/live` answering without the run ends it; a failed
 * answer is not an ending. */
async function poll() {
  if (!liveId) return;
  if (!document.hidden) {
    const running = await api<{ id: string }[]>('/api/live').catch(() => null);
    if (running && !running.some(r => r.id === liveId)) liveId = null; // ended: one last read
    await load();
  }
  if (liveId) setTimeout(poll, REFRESH_S * 1000);
}

render();
await load();
if (liveId) setTimeout(poll, REFRESH_S * 1000);
