// Post-run interview: ask one agent, at the tick on screen, what it knew then
// (spec docs/superpowers/specs/2026-11-03-agent-interview-design.md, mockup interview.html).
import { t } from './i18n';

export interface Summary { name: string; title: string | null; stress: number; mood: number; clock: string }
interface Turn { q: string; a: string }
interface Interview { id: string; agent: string; tick: number; clock: string; model: string; turns: Turn[]; stale: boolean; summary: Summary | null }
interface Listed { id: string; tick: number; clock: string; questions: number; stale: boolean }

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls = '', text = '') => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text) node.textContent = text;
  return node;
};

async function call<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error((data as { error?: string }).error ?? `${response.status}`);
  return data as T;
}

/** A sheet in #side that covers the inspect panel and the tabs while it is open. */
export class InterviewPanel {
  private root = document.getElementById('interview-panel')!;
  private current: Interview | null = null;
  private agent = '';
  private tick = 0;
  private model = '';

  /** `describe` gives the agent as the viewer shows it now, until the server's summary arrives. */
  constructor(private run: () => string | null, private describe: (agent: string) => Summary,
              private onClose: () => void) {}

  get open() { return !this.root.hidden; }

  async start(agent: string, tick: number) {
    this.agent = agent;
    this.tick = tick;
    this.current = null;
    this.show(true);
    const s = await call<{ provider: string; model_speak: string }>('/api/settings').catch(() => null);
    this.model = s ? (s.provider === 'openai' ? `OpenAI ${s.model_speak}` : 'Demo') : '';
    await this.render();
  }

  close() {
    this.show(false);
    this.onClose();
  }

  private show(on: boolean) {
    this.root.hidden = !on;
    document.getElementById('inspect-panel')!.classList.toggle('covered', on);
    document.querySelector('#side .board')!.classList.toggle('covered', on);
  }

  private base() {
    return `/api/runs/${this.run()}/interviews`;
  }

  private async render(error = '') {
    const run = this.run();
    if (!run) return;
    const list = await call<Listed[]>(`${this.base()}?agent=${encodeURIComponent(this.agent)}`).catch(() => []);
    const head = el('div', 'iv-head');
    const close = el('button', 'icon', '×');
    close.title = t('close');
    close.onclick = () => this.close();
    const s = this.current?.summary ?? this.describe(this.agent);
    head.append(el('div', 'iv-title'), close);
    head.firstElementChild!.append(el('h2', '', s?.name ?? this.agent),
      el('small', 'muted', s ? `${s.title ?? ''} · ${t('stress')} ${s.stress.toFixed(2)} · ${t('mood')} ${s.mood >= 0 ? '+' : ''}${s.mood.toFixed(2)}` : ''));
    const when = el('div', 'iv-when');
    when.append(el('span', 'iv-tag', t('interviewWhen', { clock: this.current?.clock ?? s?.clock ?? `t${this.tick}` })));
    const past = el('select', 'iv-past');
    past.append(new Option(t('interviewNew'), ''));
    for (const r of list) past.append(new Option(`${r.clock} · ${t('questionsN', { n: r.questions })}`, r.id, false, r.id === this.current?.id));
    past.onchange = async () => {
      this.current = past.value ? await call<Interview>(`${this.base()}/${encodeURIComponent(past.value)}`) : null;
      await this.render();
    };
    when.append(past);
    const msgs = el('div', 'iv-msgs');
    msgs.append(el('div', 'iv-sys', t('interviewNote')));
    if (this.current?.stale) msgs.append(el('div', 'iv-sys warn', t('interviewStale')));
    for (const turn of this.current?.turns ?? []) msgs.append(el('div', 'iv-me', turn.q), el('div', 'iv-ag', turn.a));
    if (error) msgs.append(el('div', 'iv-sys warn', error));
    const cost = el('div', 'iv-cost', t('interviewCost', { model: this.model }));
    const input = el('input');
    input.placeholder = t('interviewAsk', { name: s?.name ?? this.agent });
    const send = el('button', 'iv-send', t('send'));
    const go = async () => {
      const q = input.value.trim();
      if (!q || send.disabled) return;
      send.disabled = input.disabled = true;
      msgs.append(el('div', 'iv-me', q), el('div', 'iv-ag pending', '…'));
      msgs.scrollTop = msgs.scrollHeight;
      try {
        if (!this.current) {
          this.current = await call<Interview>(this.base(), { agent: this.agent, tick: this.tick });
          this.current.turns = [];
        }
        const turn = await call<Turn>(`${this.base()}/${encodeURIComponent(this.current.id)}/ask`, { question: q });
        this.current.turns.push(turn);
        await this.render();
      } catch (e) {
        await this.render(String(e instanceof Error ? e.message : e));
      }
    };
    send.onclick = go;
    input.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing) void go(); };
    const bar = el('div', 'iv-input');
    bar.append(input, send);
    this.root.replaceChildren(head, when, msgs, cost, bar);
    msgs.scrollTop = msgs.scrollHeight;
    input.focus();
  }
}
