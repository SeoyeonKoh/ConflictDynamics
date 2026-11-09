// The schedule tab: every agent's day plan as it stands at the tick on screen. "All" is one
// row per person across the working day; picking a person lists their blocks with times.
import { t } from './i18n';
import type { Block, World } from './world';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls = '', text = '') => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text) node.textContent = text;
  return node;
};

/** Same families as the status dot over each head. */
const FAMILY: Record<string, string> = {
  work: 'work', help: 'work',
  talk: 'talk', chat: 'talk', message: 'talk', report: 'talk', gossip: 'talk', ask_help: 'talk',
  approve: 'lead', reject: 'lead', assign: 'lead', request: 'lead', evaluate: 'lead',
  eat: 'eat', rest: 'rest', move: 'move', leave: 'move',
};
const family = (kind: string) => FAMILY[kind] ?? 'rest';

export class PlanTab {
  /** null: everyone; else one agent's id. */
  private who: string | null = null;

  constructor(private world: World, private box: HTMLElement, private pick: (agent: string) => void) {}

  /** Selecting someone on the map opens their schedule here. */
  follow(agent: string | null) {
    if (agent) this.who = agent;
  }

  render() {
    const { hello, frame } = this.world;
    if (!hello || !frame) return this.box.replaceChildren(el('p', 'muted', t('waiting')));
    const span = hello.config.ticks_per_day;
    const day = Math.floor(frame.tick / span) * span;
    const clock = (tick: number) => {
      const m = 9 * 60 + 15 * (tick - day);
      return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
    };
    const name = (id: string) => this.world.people.get(id)?.name ?? id;
    const agents = hello.agents.map(a => a.id);

    const head = el('div', 'plan-head');
    const pickBox = el('select', 'plan-who') as HTMLSelectElement;
    pickBox.append(new Option(t('planAll'), ''));
    for (const id of agents) pickBox.append(new Option(name(id), id, false, id === this.who));
    pickBox.onchange = () => { this.who = pickBox.value || null; this.render(); };
    head.append(pickBox, el('span', 'muted', t('planNow', { clock: clock(frame.tick) })));

    if (![...this.world.plans.values()].some(b => b.length)) {
      return this.box.replaceChildren(head, el('p', 'muted plan-empty', t('planNone')));
    }
    const body = this.who ? this.person(this.who, frame.tick, clock) : this.everyone(agents, day, span, frame.tick, name);
    this.box.replaceChildren(head, body);
  }

  /** One row per person; blocks laid on the day, a line at the tick on screen. */
  private everyone(agents: string[], day: number, span: number, now: number, name: (id: string) => string) {
    const grid = el('div', 'plan-grid');
    const scale = el('div', 'plan-row plan-scale');
    scale.append(el('span', 'plan-name'));
    const track = el('div', 'plan-track');
    for (let h = 0; h * 4 < span; h += 2) { // a mark every two hours
      const mark = el('span', 'plan-hour', `${9 + h}`);
      mark.style.left = `${(h * 4 / span) * 100}%`;
      track.append(mark);
    }
    scale.append(track);
    grid.append(scale);
    for (const id of agents) {
      const row = el('button', 'plan-row');
      row.type = 'button';
      row.title = t('planOpen', { name: name(id) });
      row.onclick = () => { this.who = id; this.pick(id); this.render(); };
      row.append(el('span', 'plan-name', name(id)));
      const bar = el('div', 'plan-track');
      for (const b of this.world.plans.get(id) ?? []) {
        const seg = el('span', `plan-seg ${family(b.kind)}${b.until <= now ? ' past' : ''}`);
        seg.style.left = `${((b.start - day) / span) * 100}%`;
        seg.style.width = `${((b.until - b.start) / span) * 100}%`;
        seg.title = `${b.kind} · ${b.text}`;
        bar.append(seg);
      }
      const line = el('span', 'plan-now');
      line.style.left = `${((now - day + 0.5) / span) * 100}%`;
      bar.append(line);
      row.append(bar);
      grid.append(row);
    }
    return grid;
  }

  /** One person's blocks in order, with times; the one running now stands out. */
  private person(id: string, now: number, clock: (tick: number) => string) {
    const list = el('ol', 'plan-list');
    const blocks: Block[] = this.world.plans.get(id) ?? [];
    if (!blocks.length) list.append(el('li', 'muted', t('planNoneFor')));
    for (const b of blocks) {
      const state = b.until <= now ? 'past' : b.start <= now ? 'now' : '';
      const item = el('li', `plan-item ${family(b.kind)} ${state}`);
      const when = el('div', 'plan-when', `${clock(b.start)}–${clock(b.until)}`);
      const what = el('div', 'plan-what');
      const tags = [b.kind, b.task, b.place, b.target].filter(Boolean).join(' · ');
      what.append(el('div', 'plan-kind', tags), el('div', 'plan-text', b.text));
      item.append(when, what);
      list.append(item);
    }
    return list;
  }
}
