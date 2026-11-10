// The menu page: live run, replay, scenario creation and settings.
// Mockups: docs/superpowers/specs/2026-11-03-viz-main-menu/*.html
import { t, translate, type Key } from './i18n';
import { applyTheme, getLang, getTheme, setLang, setTheme, type Lang, type Theme } from './prefs';
import { api, dialog, h, segmented } from './ui';

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
  paused_tick: number | null; live: { id: string; port: number } | null; tape: boolean;
}
export interface LiveRun { id: string; run: string; port: number; scenario: string | null; tick: number | null; day: number | null; status: string }

/** Opens a dialog's frame at once while its data loads, so a click always answers; a load
 * quicker than a blink shows nothing. Returns what closes it once the real dialog is ready. */
function loading(title: string): () => void {
  let frame: HTMLDialogElement | null = null;
  const timer = setTimeout(() => {
    frame = dialog(title, [h('p', { class: 'hint loading' }, t('loading'))], []);
  }, 120);
  return () => {
    clearTimeout(timer);
    frame?.close();
  };
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

// Line icons in the viewer's style (24 grid, round 2px strokes); `fill` ones are solid shapes.
const ICONS = {
  play: '<path fill="currentColor" stroke="none" d="M8 5.5v13a1 1 0 0 0 1.5.86l10-6.5a1 1 0 0 0 0-1.72l-10-6.5A1 1 0 0 0 8 5.5z"/>',
  replay: '<path d="M3.5 12a8.5 8.5 0 1 0 2.7-6.2"/><path d="M3.5 4v4.5H8"/><path d="M12 8v4.2l2.8 1.8"/>',
  create: '<path d="M12 5v14M5 12h14"/>',
  settings: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
};
function icon(name: keyof typeof ICONS, cls = ''): HTMLElement {
  const box = h('span', { class: cls, 'aria-hidden': 'true' });
  box.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
  return box;
}

async function sprite(n: number): Promise<HTMLElement> {
  const el = h('div', { class: 'sprite' });
  try {
    const atlas = await (await fetch(`/assets/characters-v5/agent-${n}.atlas.json`)).json();
    const f = atlas.frames['idle-0'].frame, size = atlas.meta.size;
    const k = Math.max(1, Math.floor(Math.min(innerHeight * 0.2, 170) / f.h)); // whole pixels stay crisp
    Object.assign(el.style, {
      width: `${f.w * k}px`, height: `${f.h * k}px`, backgroundImage: `url(/assets/characters-v5/${atlas.meta.image})`,
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
  // One word per button and a short count at its end; the long story lives in the dialogs.
  const card = (cls: string, glyph: keyof typeof ICONS, title: Key, meta: HTMLElement, hint: Key) =>
    h('button', { class: `choice ${cls}`, type: 'button', title: t(hint) }, icon(glyph, 'icon'),
      h('h2', {}, t(title)), meta);
  const live = card('live', 'play', 'live', liveMeta, 'liveDesc');
  const replay = card('replay', 'replay', 'replay', replayMeta, 'replayDesc');
  const createMeta = h('div', { class: 'meta' });
  const create = card('create', 'create', 'create', createMeta, 'createDesc');
  const settings = h('button', { type: 'button' }, icon('settings'), t('settings'));
  root.replaceChildren(scene, h('div', { class: 'menu' },
    h('header', { class: 'menu-head' }, h('div', { class: 'kicker' }, t('kicker')), h('h1', {}, t('title'))),
    h('div', { class: 'menu-body' }, h('div', { class: 'choices' }, live, replay, create),
      h('div', { class: 'minor' }, settings))));
  crowd.append(...(await Promise.all(SPRITES.map(sprite))));

  let running: LiveRun[] = [];
  live.onclick = () => (running.length === 1 ? (location.href = `/view.html?live=${running[0].id}`) : openLiveSetup(running));
  replay.onclick = () => openReplayPicker();
  create.onclick = () => { location.href = '/create.html'; };
  settings.onclick = () => openSettings();
  api<{ id: string }[]>('/api/drafts')
    .then(drafts => { createMeta.textContent = drafts.length ? t('draftsN', { n: drafts.length }) : ''; })
    .catch(() => { /* an older server: no count */ });
  try {
    running = await api<LiveRun[]>('/api/live');
    const { runs } = await api<{ runs: RunRow[] }>('/api/runs');
    if (running.length) {
      const r = running[0];
      liveMeta.replaceChildren(h('span', { class: 'dot' }), t('runningN', { n: running.length }));
      liveMeta.title = `${r.scenario ?? ''} ${r.tick === null ? '' : t('dayClock', { day: (r.day ?? 0) + 1, clock: clock(r.tick) })}`;
    }
    replayMeta.textContent = runs.length ? t('runsN', { n: runs.length }) : '';
    if (runs.length) replayMeta.title = t('lastOn', { date: new Date(runs[0].modified / 1e6).toLocaleDateString(getLang()) });
  } catch {
    replayMeta.textContent = 'conflict-server?';
  }
}

// ---- settings ----
export async function openSettings() {
  const ready = loading(t('settings'));
  const s = await api<Settings>('/api/settings').finally(ready);
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
    void home();
  };
}

// ---- paid confirmation ----
/** An OpenAI run starts only after this says yes; Demo needs no confirmation. */
export function confirmPaid(provider: string, estimate: string, cap: number | null): Promise<boolean> {
  if (provider !== 'openai') return Promise.resolve(true);
  return new Promise(resolve => {
    const no = h('button', { type: 'button' }, t('cancel'));
    const go = h('button', { type: 'button', class: 'primary-btn' }, t('confirmGo'));
    const d = dialog(t('confirmTitle'), [
      h('p', {}, t('confirmBody', { estimate, cap: cap === null ? t('unlimited') : cap.toLocaleString() })),
      cap === null ? h('p', { class: 'hint warn' }, t('confirmUnlimited')) : null,
    ], [no, go]);
    let answer = false;
    no.onclick = () => d.close();
    go.onclick = () => { answer = true; d.close(); };
    d.addEventListener('close', () => resolve(answer));
  });
}

// ---- replay ----
const stateLabel = (row: RunRow): [string, string] =>
  row.live ? [t('running'), 'run'] : row.status === 'completed' ? [t('done'), 'ok']
    : row.status === 'paused' ? [t('paused'), 'pause'] : row.status === 'failed' ? [t('failed'), 'bad'] : [row.status, 'pause'];

export async function openReplayPicker() {
  const ready = loading(t('replay'));
  const { runs } = await api<{ runs: RunRow[] }>('/api/runs').finally(ready);
  const name = (row: RunRow) => row.run.split('/')[0];
  let picked: RunRow | null = null, query = '', scenario = '';
  const search = h('input', { class: 'search', placeholder: t('searchRuns') }) as HTMLInputElement;
  const chips = h('div', { class: 'chips' });
  const scenarios = [...new Set(runs.map(r => r.scenario).filter((s): s is string => !!s))];
  for (const s of ['', ...scenarios]) {
    const b = h('button', { type: 'button', class: s === scenario ? 'on' : '' }, s || t('all'));
    b.onclick = () => { scenario = s; chips.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); draw(); };
    chips.append(b);
  }
  const body = h('tbody');
  const note = h('span', { class: 'note' }, t('pickHint'));
  const resume = h('button', { type: 'button' }, t('resumeRun'));
  const open = h('button', { type: 'button', class: 'primary-btn' }, t('openReplay'));
  resume.hidden = true;
  open.disabled = true;
  const draw = () => {
    const q = query.toLowerCase();
    body.replaceChildren(...runs
      .filter(r => (!scenario || r.scenario === scenario) && (!q || r.run.toLowerCase().includes(q) || (r.scenario ?? '').toLowerCase().includes(q)))
      .map(r => {
        const [label, cls] = stateLabel(r);
        const tr = h('tr', { class: r === picked ? 'sel' : '' },
          h('td', {}, h('b', {}, name(r)), h('small', {}, r.scenario ?? '-')),
          h('td', {}, h('span', { class: `st ${cls}` }, label)),
          h('td', {}, t('lengthDays', { days: r.days.toFixed(1).replace(/\.0$/, ''), ticks: r.ticks + 1 })),
          h('td', { class: 'hide-narrow' }, r.model ?? '-'),
          h('td', { class: 'num hide-narrow' }, `${(r.tokens / 1e6).toFixed(2)}M`),
          h('td', { class: 'num' }, new Date(r.modified / 1e6).toLocaleString(getLang(), { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })));
        tr.onclick = () => { picked = r; draw(); };
        tr.ondblclick = () => go(r);
        return tr;
      }));
    note.textContent = picked ? t('picked', { run: name(picked) }) : t('pickHint');
    open.disabled = !picked;
    resume.hidden = !(picked && !picked.live && picked.status === 'paused' && picked.resumable);
  };
  const go = (r: RunRow) => { location.href = r.live ? `/view.html?live=${r.live.id}` : `/view.html?replay=${r.run}`; };
  search.oninput = () => { query = search.value; draw(); };
  open.onclick = () => picked && go(picked);
  resume.onclick = () => picked && openResume(picked);
  const table = h('table', {}, h('thead', {}, h('tr', {}, ...(['colRun', 'colState', 'colLength', 'colModel', 'colTokens', 'colDate'] as Key[])
    .map((k, i) => h('th', { class: [i >= 4 ? 'num' : '', i === 3 || i === 4 ? 'hide-narrow' : ''].join(' ') }, t(k))))), body);
  const back = h('button', { type: 'button' }, t('back'));
  const d = dialog(t('pickRun'), [h('div', { class: 'tools' }, search, chips), h('div', { class: 'list' }, table)],
    [note, h('span', { class: 'spacer' }), back, resume, open], true);
  d.querySelector('.d-foot')!.classList.add('split');
  back.onclick = () => d.close();
  draw();
}

async function openResume(row: RunRow) {
  const s = await api<Settings>('/api/settings');
  const hint = h('div', { class: 'hint' });
  const cap = capInput(s.max_total_tokens, hint);
  const cancel = h('button', { type: 'button' }, t('cancel'));
  const go = h('button', { type: 'button', class: 'primary-btn' }, t('resumeRun'));
  const d = dialog(t('resumeRun'), [h('p', {}, row.run),
    h('div', { class: 'field' }, h('label', {}, t('cap')), cap.el), hint,
    row.tape ? null : h('p', { class: 'hint warn' }, t('resumeOld'))], [cancel, go]);
  cancel.onclick = () => d.close();
  go.onclick = async () => {
    const limit = cap.value();
    if (!(await confirmPaid(row.backend ?? 'demo', row.scenario ?? '', limit))) return;
    go.disabled = true; // one resume at a time: the server also refuses a second one
    try {
      const started = await api<{ id: string }>(`/api/runs/${row.run}/resume`, {
        method: 'POST', body: { max_total_tokens: limit, paid_confirmed: row.backend === 'openai' },
      });
      location.href = `/view.html?live=${started.id}`;
    } catch (error) {
      go.disabled = false;
      hint.className = 'hint warn';
      hint.textContent = String(error);
    }
  };
}

// ---- live ----
interface Scenario { name: string; research_question: string; extends: string | null; max_days: number; estimated_calls: number; tokens_per_day: number | null }

export async function openLiveSetup(running: LiveRun[] = [], preselect?: string) {
  const ready = loading(t('live'));
  const [catalog, s] = await Promise.all([api<Scenario[]>('/api/scenarios'), api<Settings>('/api/settings')])
    .finally(ready);
  let picked = catalog.find(sc => sc.name === preselect) ?? catalog[0], days = picked?.max_days ?? 1;
  const list = h('div', { class: 'scl' });
  const empty = h('div', { class: 'empty' }, t('noScenario'));
  empty.hidden = true;
  const daysOut = h('output', {}, t('dayN', { n: days }));
  const defaultHint = h('div', { class: 'hint' });
  const estimate = h('div', { class: 'est' });
  const capHint = h('div', { class: 'hint' });
  const cap = capInput(s.max_total_tokens, capHint);
  const usage = () => {
    const calls = Math.round((picked.estimated_calls / Math.max(1, picked.max_days)) * days).toLocaleString();
    return picked.tokens_per_day
      ? t('estimate', { tokens: `${((picked.tokens_per_day * days) / 1e6).toFixed(1)}M`, calls })
      : t('estimateCalls', { calls });
  };
  const refresh = () => {
    daysOut.textContent = t('dayN', { n: days });
    defaultHint.textContent = t('scenarioDefault', { n: picked.max_days });
    estimate.textContent = usage();
  };
  const cards = catalog.map(sc => {
    const b = h('button', { type: 'button', class: `sc${sc === picked ? ' on' : ''}` }, h('b', {}, sc.name),
      h('small', {}, sc.research_question), sc.extends ? h('em', {}, `← ${sc.extends}`) : null);
    b.onclick = () => {
      picked = sc;
      days = sc.max_days;
      list.querySelectorAll('.sc').forEach(x => x.classList.toggle('on', x === b));
      refresh();
    };
    return b;
  });
  list.append(...cards, empty);
  const search = h('input', { class: 'search', placeholder: t('searchScenario') }) as HTMLInputElement;
  search.oninput = () => {
    const q = search.value.trim().toLowerCase();
    let shown = 0;
    cards.forEach((c, i) => { c.hidden = !catalog[i].name.toLowerCase().includes(q); shown += Number(!c.hidden); });
    empty.hidden = shown > 0;
  };
  const minus = h('button', { type: 'button' }, '−'), plus = h('button', { type: 'button' }, '+');
  minus.onclick = () => { days = Math.max(1, days - 1); refresh(); };
  plus.onclick = () => { days = Math.min(10, days + 1); refresh(); };
  const toSettings = h('a', { href: '#' }, t('changeInSettings'));
  const providerName = s.provider === 'openai' ? `OpenAI · ${s.model_decide}` : 'Demo';
  const back = h('button', { type: 'button' }, t('back'));
  const start = h('button', { type: 'button', class: 'primary-btn' }, t('startRun'));
  const runningList = running.length ? h('div', { class: 'running' }, ...running.map(r =>
    h('a', { href: `/view.html?live=${r.id}` }, h('span', { class: 'dot' }), `${r.scenario ?? r.id}${r.tick === null ? '' : ` · ${t('dayClock', { day: (r.day ?? 0) + 1, clock: clock(r.tick) })}`}`))) : null;
  const d = dialog(t('live'), [runningList, h('div', { class: 'grid' },
    h('div', {}, h('div', { class: 'label' }, t('scenario')), search, list),
    h('div', {}, h('div', { class: 'label' }, t('runSetup')),
      h('div', { class: 'row' }, h('span', {}, t('days')), h('div', { class: 'stepper' }, minus, daysOut, plus)), defaultHint,
      h('div', { class: 'field' }, h('label', {}, t('cap')), cap.el), capHint, estimate,
      h('div', { class: 'prov-line' }, h('span', {}, t('providerLine', { p: providerName })), toSettings)))],
  [back, start], true);
  toSettings.onclick = e => { e.preventDefault(); d.close(); void openSettings(); };
  back.onclick = () => d.close();
  start.onclick = async () => {
    const limit = cap.value();
    if (!(await confirmPaid(s.provider, usage(), limit))) return;
    start.disabled = true;
    try {
      const started = await api<{ id: string }>('/api/live', { method: 'POST', body: {
        scenario: picked.name, days, max_total_tokens: limit, paid_confirmed: s.provider === 'openai',
      } });
      location.href = `/view.html?live=${started.id}`;
    } catch (error) {
      start.disabled = false;
      estimate.textContent = String(error);
    }
  };
  refresh();
  list.querySelector('.sc.on')?.scrollIntoView({ block: 'nearest' });
}

void home().then(() => {  // `#settings`, `#replay`, `#live` open that dialog: links and screenshots
  // `#live=<scenario>` (the generator's "run it live" link) opens the live dialog on that scenario.
  // A hash, not `?live=`, which old viewer links still use for a running run's id.
  if (location.hash.startsWith('#live=')) {
    const scenario = decodeURIComponent(location.hash.slice('#live='.length));
    history.replaceState(null, '', location.pathname);
    void openLiveSetup([], scenario);
    return;
  }
  const open = { '#settings': openSettings, '#replay': openReplayPicker, '#live': () => openLiveSetup() }[location.hash];
  if (open) void open();
});
