// The menu page: live run, replay, scenario creation (coming soon) and settings.
// Mockups: docs/superpowers/specs/2026-11-03-viz-main-menu/*.html
import { t, translate, type Key } from './i18n';
import { applyTheme, getLang, getTheme, setLang, setTheme, type Lang, type Theme } from './prefs';

// Old links (`/?replay=…`, `/?ws=…`) open the viewer as they used to.
const params = new URLSearchParams(location.search);
if (params.has('replay') || params.has('ws') || params.has('live')) {
  location.replace('/view.html' + location.search);
}
applyTheme();

// ---- server ----
export interface Settings {
  provider: 'openai' | 'demo'; model_decide: string; model_speak: string; model_embed: string;
  max_total_tokens: number | null; openai_key: boolean;
}
export interface RunRow {
  run: string; scenario: string | null; status: string; model: string | null; backend: string | null;
  ticks: number; days: number; tokens: number; modified: number; resumable: boolean;
  paused_tick: number | null; live: { id: string; port: number } | null;
}
export interface LiveRun { id: string; run: string; port: number; scenario: string | null; tick: number | null; day: number | null; status: string }

export async function api<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const response = await fetch(path, {
    method: init?.method ?? 'GET',
    headers: init?.body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error((data as { error?: string }).error ?? `${response.status}`);
  return data as T;
}

// ---- small DOM helpers ----
export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K, attrs: Record<string, string> = {}, ...children: (Node | string | null)[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') el.className = v; else el.setAttribute(k, v);
  }
  for (const c of children) if (c !== null) el.append(c);
  return el;
}

export function dialog(title: string, body: Node[], foot: Node[], wide = false): HTMLDialogElement {
  const close = h('button', { class: 'x', title: t('close') }, '×');
  const d = h('dialog', { class: `panel${wide ? ' wide' : ''}` },
    h('div', { class: 'd-head' }, h('h1', {}, title), close), ...body, h('div', { class: 'd-foot' }, ...foot));
  close.onclick = () => d.close();
  d.addEventListener('click', e => { if (e.target === d) d.close(); }); // a click on the backdrop
  d.addEventListener('close', () => d.remove());
  document.body.append(d);
  d.showModal();
  return d;
}

export function segmented<T extends string>(options: [T, Key][], value: T, onPick: (v: T) => void): HTMLElement {
  const seg = h('div', { class: 'seg' });
  for (const [v, key] of options) {
    const b = h('button', { type: 'button', class: v === value ? 'on' : '' }, t(key));
    b.onclick = () => {
      seg.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
      onPick(v);
    };
    seg.append(b);
  }
  return seg;
}

/** A token cap input with a cap/unlimited switch; `value()` is null for unlimited. */
export function capInput(initial: number | null, hint?: HTMLElement) {
  const input = h('input', { inputmode: 'numeric' }) as HTMLInputElement;
  let unlimited = initial === null;
  const show = () => {
    input.disabled = unlimited;
    input.value = unlimited ? t('unlimited') : (initial ?? 2_000_000).toLocaleString();
    if (hint) {
      hint.className = unlimited ? 'hint warn' : 'hint';
      hint.textContent = unlimited ? t('unlimitedHint') : t('capHint');
    }
  };
  const seg = segmented<'cap' | 'none'>([['cap', 'capped'], ['none', 'unlimited']], unlimited ? 'none' : 'cap', v => {
    if (!unlimited) initial = Number(input.value.replace(/\D/g, '')) || initial;
    unlimited = v === 'none';
    show();
  });
  show();
  return {
    el: h('div', { class: 'keyrow' }, input, seg),
    value: (): number | null => (unlimited ? null : Number(input.value.replace(/\D/g, '')) || null),
  };
}

// ---- home ----
const SPRITES = [0, 3, 5, 8, 11, 14];

async function sprite(n: number): Promise<HTMLElement> {
  const el = h('div', { class: 'sprite' });
  try {
    const atlas = await (await fetch(`/assets/characters-v4/agent-${n}.atlas.json`)).json();
    const f = atlas.frames['idle-0'].frame, size = atlas.meta.size;
    const height = Math.min(innerHeight * 0.2, 170), k = height / f.h;
    Object.assign(el.style, {
      width: `${f.w * k}px`, backgroundImage: `url(/assets/characters-v4/${atlas.meta.image})`,
      backgroundSize: `${size.w * k}px ${size.h * k}px`, backgroundPosition: `${-f.x * k}px ${-f.y * k}px`,
    });
  } catch { /* no art: an empty slot */ }
  return el;
}

const clock = (tick: number, ticksPerDay = 34) => {
  const minutes = 9 * 60 + 15 * (tick % ticksPerDay);
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
};

async function home() {
  const root = document.getElementById('menu-root')!;
  const crowd = h('div', { class: 'crowd' });
  const scene = h('div', { class: 'scene' }, h('div', { class: 'floor' }), crowd,
    h('div', { class: 'menu-bubble', style: 'left:18%;bottom:30%;animation-delay:-1s' }, '출시 계획 끝났나요?'),
    h('div', { class: 'menu-bubble', style: 'right:20%;bottom:33%;animation-delay:-3.5s' }, '검토 올렸어요'));
  const liveMeta = h('div', { class: 'meta' });
  const replayMeta = h('div', { class: 'meta' });
  const card = (cls: string, icon: string, title: Key, desc: Key, meta: HTMLElement, extra: Node | null = null) =>
    h('button', { class: `choice ${cls}`, type: 'button' }, h('div', { class: 'icon' }, icon),
      h('h2', {}, t(title), extra), h('p', {}, t(desc)), meta);
  const live = card('live', '▶', 'live', 'liveDesc', liveMeta);
  const replay = card('replay', '⟲', 'replay', 'replayDesc', replayMeta);
  const create = card('create', '✦', 'create', 'createDesc', h('div', { class: 'meta' }, t('createFlow')),
    h('span', { class: 'soon' }, t('soon')));
  const settings = h('button', { type: 'button' }, `⚙ ${t('settings')}`);
  root.replaceChildren(scene, h('div', { class: 'menu' },
    h('div', { class: 'kicker' }, t('kicker')), h('h1', {}, t('title')), h('p', { class: 'tag' }, t('tagline')),
    h('div', { class: 'choices' }, live, replay, create), h('div', { class: 'minor' }, settings)));
  crowd.append(...(await Promise.all(SPRITES.map(sprite))));

  let running: LiveRun[] = [];
  live.onclick = () => (running.length === 1 ? (location.href = `/view.html?live=${running[0].id}`) : openLiveSetup(running));
  replay.onclick = () => openReplayPicker();
  settings.onclick = () => openSettings();
  try {
    running = await api<LiveRun[]>('/api/live');
    const { runs } = await api<{ runs: RunRow[] }>('/api/runs');
    if (running.length) {
      const r = running[0];
      liveMeta.replaceChildren(h('span', { class: 'dot' }),
        `${t('runningN', { n: running.length })} · ${r.scenario ?? ''} ${r.tick === null ? '' : t('dayClock', { day: (r.day ?? 0) + 1, clock: clock(r.tick) })}`);
    } else if (runs[0]) {
      liveMeta.textContent = `${runs[0].scenario ?? ''} · ${runs[0].model ?? ''}`;
    }
    replayMeta.textContent = runs.length
      ? `${t('savedRuns', { n: runs.length })} · ${t('lastOn', { date: new Date(runs[0].modified / 1e6).toLocaleDateString(getLang()) })}`
      : t('noRuns');
  } catch {
    replayMeta.textContent = 'conflict-server?';
  }
}

// ---- settings ----
export async function openSettings() {
  const s = await api<Settings>('/api/settings');
  const rerender = () => { translate(); void home(); };
  const lang = segmented<Lang>([['ko', 'uiLang'], ['en', 'uiLang']], getLang(), v => { setLang(v); rerender(); });
  lang.querySelectorAll('button')[0].textContent = '한국어';
  lang.querySelectorAll('button')[1].textContent = 'English';
  const theme = segmented<Theme>([['light', 'light'], ['dark', 'dark'], ['system', 'system']], getTheme(), setTheme);

  let provider = s.provider;
  const prov = (id: string, name: string, desc: Key, enabled: boolean) => {
    const b = h('button', { type: 'button', class: `prov${id === provider ? ' on' : ''}` },
      enabled ? null : h('span', { class: 'soon' }, t('soon')), h('b', {}, name), h('small', {}, t(desc)));
    if (!enabled) b.disabled = true;
    b.onclick = () => {
      provider = id as Settings['provider'];
      providers.querySelectorAll('.prov').forEach(x => x.classList.toggle('on', x === b));
      openaiFields.hidden = provider !== 'openai';
      demoFields.hidden = provider !== 'demo';
    };
    return b;
  };
  const providers = h('div', { class: 'providers' }, prov('openai', 'OpenAI', 'realApi', true),
    prov('demo', 'Demo', 'demoDesc', true), prov('anthropic', 'Anthropic', 'soon', false),
    prov('google', 'Google', 'soon', false), prov('local', t('local'), 'localDesc', false));
  const model = (key: Key, value: string) => {
    const input = h('input', { value }) as HTMLInputElement;
    return { input, el: h('div', { class: 'field' }, h('label', {}, t(key)), input) };
  };
  const decide = model('modelDecide', s.model_decide), speak = model('modelSpeak', s.model_speak);
  const embed = model('modelEmbed', s.model_embed);
  const cap = capInput(s.max_total_tokens);
  const key = h('div', { class: 'keyrow' }, h('input', { type: 'password', value: s.openai_key ? 'sk-••••••••••••' : '', readonly: '' }),
    s.openai_key ? h('span', { class: 'status-ok' }, h('span', { class: 'dot' }), t('keyFromEnv'))
      : h('span', { class: 'status-bad' }, t('noKey')));
  const openaiFields = h('div', {}, h('div', { class: 'field' }, h('label', {}, t('apiKey')), key),
    h('div', { class: 'two' }, decide.el, speak.el), embed.el,
    h('div', { class: 'field' }, h('label', {}, t('defaultCap')), cap.el), h('div', { class: 'hint warn' }, t('costNote')));
  const demoFields = h('div', {}, h('div', { class: 'hint' }, t('demoNote')));
  openaiFields.hidden = provider !== 'openai';
  demoFields.hidden = provider !== 'demo';

  const cancel = h('button', { type: 'button' }, t('cancel'));
  const save = h('button', { type: 'button', class: 'primary-btn' }, t('save'));
  const d = dialog(t('settings'), [
    h('div', { class: 'sec' }, h('div', { class: 'label' }, t('screen')),
      h('div', { class: 'row' }, h('span', {}, t('uiLang')), lang),
      h('div', { class: 'row' }, h('span', {}, t('theme')), theme)),
    h('div', { class: 'sec' }, h('div', { class: 'label' }, t('provider')), providers, openaiFields, demoFields),
  ], [cancel, save]);
  cancel.onclick = () => d.close();
  save.onclick = async () => {
    await api('/api/settings', { method: 'PUT', body: {
      provider, model_decide: decide.input.value.trim(), model_speak: speak.input.value.trim(),
      model_embed: embed.input.value.trim(), max_total_tokens: cap.value(),
    } });
    d.close();
    void home().then(() => {  // `#settings`, `#replay`, `#live` open that dialog: links and screenshots
  const open = { '#settings': openSettings, '#replay': openReplayPicker, '#live': () => openLiveSetup() }[location.hash];
  if (open) void open();
});
  };
}

// Filled in by the replay and live tasks.
export async function openReplayPicker() {}
export async function openLiveSetup(_running: LiveRun[] = []) {}

void home().then(() => {  // `#settings`, `#replay`, `#live` open that dialog: links and screenshots
  const open = { '#settings': openSettings, '#replay': openReplayPicker, '#live': () => openLiveSetup() }[location.hash];
  if (open) void open();
});
