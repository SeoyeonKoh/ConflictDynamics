// The conversation tab: every talk, meeting and message as one thread, read start to end, with
// the thought behind each line behind a toggle (spec 5.5, mockup conversation.html).
import { t } from './i18n';
import type { EngineEvent } from './messages';
import type { World } from './world';

export interface Line { tick: number; speaker: string; text: string; session: string; id?: string; thought?: string }
export interface SessionInfo { kind: string; place: string | null; participants: string[] }
export interface Conversation {
  id: string; kind: 'talk' | 'meeting' | 'message'; place: string | null;
  participants: string[]; first: number; last: number; lines: Line[];
}

const kindOf = (id: string): Conversation['kind'] =>
  id.startsWith('meeting:') ? 'meeting' : id.startsWith('dm:') ? 'message' : 'talk';

/** Lines grouped by conversation, the most recently started first. */
export function conversations(lines: Line[], sessions: Map<string, SessionInfo>): Conversation[] {
  const by = new Map<string, Conversation>();
  for (const line of lines) {
    let c = by.get(line.session);
    if (!c) {
      const info = sessions.get(line.session);
      // A direct message names both people in its id: dm:A:B:day.
      const named = line.session.startsWith('dm:') ? line.session.split(':').slice(1, 3) : [];
      c = { id: line.session, kind: kindOf(line.session), place: info?.place ?? null,
            participants: [...(info?.participants ?? named)], first: line.tick, last: line.tick, lines: [] };
      by.set(line.session, c);
    }
    c.lines.push(line);
    c.last = line.tick;
    if (!c.participants.includes(line.speaker)) c.participants.push(line.speaker);
  }
  return [...by.values()].sort((a, b) => b.first - a.first || (a.id < b.id ? -1 : 1));
}

/** Older journals carry no thoughts: take them from the engine log, by the same rule as the
 * engine (frames.py `_with_thoughts`): a reply's judgement by utterance id, else the speaker's
 * talk/message action of that tick for their first line in it. Meetings get none. */
export function attachThoughts(lines: Line[], events: EngineEvent[]) {
  if (!events.length || lines.some(l => l.id !== undefined)) return;
  const replied = new Map<string, string[]>(); // session|speaker → reflections in order
  const opened = new Map<string, string>(); // tick|actor → reflection
  for (const e of events) {
    const p = e.payload as Record<string, unknown>;
    if (e.kind === 'decision' && p.posted && typeof p.reflection === 'string') {
      const key = `${p.session}|${p.agent}`;
      replied.set(key, [...(replied.get(key) ?? []), p.reflection]);
    }
    if (e.kind === 'action' && (p.kind === 'talk' || p.kind === 'message') && typeof p.reflection === 'string') {
      opened.set(`${e.tick}|${e.actor}`, p.reflection);
    }
  }
  const spoke = new Set<string>();
  for (const line of lines) {
    if (line.session.startsWith('meeting:')) continue;
    const reply = replied.get(`${line.session}|${line.speaker}`);
    let thought = reply?.shift();
    const first = `${line.tick}|${line.speaker}`;
    if (thought === undefined && !spoke.has(first)) thought = opened.get(first);
    spoke.add(first);
    if (thought && thought.trim() !== line.text.trim()) line.thought = thought.trim();
  }
}

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls = '', text = '') => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text) node.textContent = text;
  return node;
};

/** Renders into the tab, keeping which conversation is open and which thoughts are unfolded. */
export class ConversationTab {
  private selected: string | null = null;
  private openThoughts = new Set<string>();
  private allOpen = false;

  constructor(private world: World, private root: HTMLElement) {}

  render() {
    const w = this.world;
    const list = conversations(w.lines, w.sessions);
    if (!list.length) {
      this.root.replaceChildren(el('p', 'muted conv-empty', t('noConversations')));
      return;
    }
    const current = list.find(c => c.id === this.selected) ?? list[0];
    this.selected = current.id;
    const span = w.hello?.config.ticks_per_day ?? 34;
    const clock = (tick: number) => {
      const m = 9 * 60 + 15 * (tick % span);
      return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
    };
    const when = (tick: number) => t('dayClock', { day: Math.floor(tick / span) + 1, clock: clock(tick) });
    const name = (id: string) => w.people.get(id)?.name ?? id;

    const items = el('div', 'conv-list');
    for (const c of list) {
      const b = el('button', `conv${c === current ? ' on' : ''}`);
      const top = el('div', 'conv-top');
      top.append(el('span', `k k-${c.kind}`, t(c.kind)), el('span', 'when', when(c.first)));
      const who = c.participants.map(name);
      b.append(top, el('b', '', who.slice(0, 4).join(' · ') + (who.length > 4 ? ` +${who.length - 4}` : '')),
        el('small', '', [c.place, t('lines', { n: c.lines.length })].filter(Boolean).join(' · ')));
      b.onclick = () => { this.selected = c.id; this.render(); };
      items.append(b);
    }

    const head = el('div', 'conv-head');
    const all = el('label', 'conv-all');
    const box = el('input');
    box.type = 'checkbox';
    box.checked = this.allOpen;
    box.onchange = () => { this.allOpen = box.checked; this.openThoughts.clear(); this.render(); };
    all.append(box, ` ${t('thoughtsAll')}`);
    head.append(el('h3', '', `${t(current.kind)}${current.place ? ` · ${current.place}` : ''}`), all);
    const thread = el('div', 'conv-thread');
    thread.append(head, el('p', 'muted', `${when(current.first)} – ${clock(current.last)} · ${current.participants.map(name).join(', ')}`));
    current.lines.forEach((line, i) => {
      const key = `${current.id}#${i}`;
      const row = el('div', 'conv-line');
      const who = el('div', 'who');
      who.append(el('b', '', name(line.speaker)), el('span', '', w.people.get(line.speaker)?.title ?? ''), el('time', '', clock(line.tick)));
      row.append(who, el('p', 'tx', line.text));
      if (line.thought) {
        const details = el('details', 'th');
        details.open = this.allOpen || this.openThoughts.has(key);
        details.append(el('summary', '', t('thought')), el('p', '', line.thought));
        details.ontoggle = () => (details.open ? this.openThoughts.add(key) : this.openThoughts.delete(key));
        row.append(details);
      } else if (current.kind === 'meeting') {
        row.append(el('div', 'th none', t('meetingNoThought')));
      }
      thread.append(row);
    });
    const scroller = this.root.querySelector('.conv-thread');
    const keepScroll = scroller && this.root.dataset.conv === current.id ? scroller.scrollTop : null;
    this.root.dataset.conv = current.id;
    this.root.replaceChildren(items, thread);
    if (keepScroll !== null) thread.scrollTop = keepScroll;
  }
}
