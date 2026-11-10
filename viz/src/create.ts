// The scenario generator's work screen: the conversation on the left, the draft's preview on the
// right (spec docs/superpowers/specs/2026-11-10-scenario-generator-design.md §5.1, mockup option B).
// `create.html?draft=<id>` opens that draft; without it the start screen lists drafts to continue.
import { t, translate, type Key } from './i18n';
import { applyTheme, getLang } from './prefs';
import { api, ApiError, dialog, h, segmented } from './ui';

applyTheme();
translate();
document.title = `${t('create')} · Conflict Dynamics`;

// ---- server shapes (src/conflict_sim/generator.py view(), scenario_draft.Version) ----
type Mode = 'scratch' | 'variant';
type Role = 'baseline' | 'variant';
interface Settings { provider: string; openai_key: boolean; model_decide?: string; generation_token_cap?: number }
interface Scenario { name: string; research_question: string; extends: string | null }
interface Listed { id: string; title: string; mode: Mode; updated: string; saved: string[] }
interface Message { role: 'user' | 'ai' | 'check'; text: string; tokens?: number }
interface Change { path: string; factor: string; a: unknown; b: unknown }
interface Person {
  id: string; name: string; department?: string; role?: string; position?: string; reports_to?: string | null;
  disc?: string; communication_style?: string; pressure_response?: string; conflict_engagement_style?: string;
}
interface Task {
  id: string; name: string; owner?: string | null; contributors?: string[]; reviewers?: string[];
  predecessors?: string[]; authority_scope?: string | null;
}
interface Step { key: string; name: string; effort_ticks: number; department?: string | null; after?: string[] }
interface Project { id: string; name: string; department: string; lead: string; due: number; start_after?: string[]; steps?: Step[] }
interface Extra {
  id: string; name: string; effort_ticks: number; due: number; owner?: string | null; assign_scope?: string | null;
  reviewers?: string[]; depends_on?: string[]; arrives?: number | null;
}
interface Meeting { id: string; day: number; tick: number; duration_ticks: number; organizer: string; participants: string[]; agenda: string }
interface Shock { id: string; day: number; tick: number; kind: string; task?: string | null; agent?: string | null; until_tick?: number | null }
interface Block { id: string; day: number; tick: number; duration_ticks: number; participants: string[]; kind: string; text: string }
interface ScenarioPart {
  task_runtime?: { id: string; effort_ticks: number; due: number }[]; projects?: Project[]; extra_tasks?: Extra[];
  engine?: { meetings?: Meeting[]; shocks?: Shock[] };
  weekly_operations?: { lunch_start_tick?: number; blocks?: Block[] } | null;
  unassigned?: string[]; ticks_per_day?: number | null; max_days?: number;
  research_question?: string; manipulated_variable?: string; fixed_variables?: string[]; manipulation_check?: string[];
}
interface Version {
  company: { organization?: string; project?: string; departments?: { id: string; name: string }[]; people?: Person[]; tasks?: Task[] };
  scenario: ScenarioPart;
}
interface Measure { metric: string; subject: string; toward?: string | null; direction: string }
interface Experiment { id?: string; factor?: string | null; hypothesis?: string; measures?: Measure[]; behaviour_checks?: string[] }
interface Draft {
  id: string; mode: Mode; source: string | null; title: string; pair: boolean; factor: string | null;
  experiment: Experiment | null; materials: { name: string; text: string }[];
  versions: Record<Role, Version | null>; messages: Message[]; saved: string[];
  checks: Record<Role, string[] | null>; diff: Change[]; outside: Change[];
  files: Partial<Record<Role, Record<string, string>>>;
}
interface Attachment { name: string; text: string }

const root = document.getElementById('create-root')!;
const ROLES: Role[] = ['baseline', 'variant'];
const EACH_LIMIT = 200_000, ALL_LIMIT = 1_000_000; // the server's attachment limits (server.py)

// ---- small helpers ----
const list = <T>(x: unknown): T[] => (Array.isArray(x) ? (x as T[]) : []);
const bytes = (text: string) => new Blob([text]).size;
const when = (iso: string) => (iso ? new Date(iso).toLocaleString(getLang(), { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');
const hhmm = (tick: number) => {
  const minutes = 9 * 60 + 15 * tick;
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`;
};
const short = (value: unknown, limit = 80) => {
  const text = value === undefined ? '—' : typeof value === 'string' ? value : JSON.stringify(value);
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
};

const SERVER_ERRORS: Record<string, Key> = {
  'the draft is busy': 'errBusy',
  'attachments are limited to 200 KB each, 1 MB in all': 'errAttachLimit',
  'fix the errors first': 'errFixFirst',
  'the variant differs outside its factor': 'errOutside',
  'write the variant first': 'errVariantFirst',
  'nothing to save yet': 'errNothing',
  'scenario generation needs the OpenAI provider': 'needOpenai',
  "no OpenAI key in the server's .env": 'needKey',
  'no such draft': 'errNoDraft',
};
const errorText = (error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  return SERVER_ERRORS[message] ? t(SERVER_ERRORS[message]) : message;
};

function toast(children: (Node | string)[], kind = '') {
  document.querySelector('.cg-toast')?.remove();
  const el = h('div', { class: `cg-toast ${kind}`, role: 'status' }, ...children);
  document.body.append(el);
  setTimeout(() => el.classList.add('out'), 8000);
  setTimeout(() => el.remove(), 8600);
}

/** A check line that reports a failure: a generation that failed or a check that did not pass. */
const failedCheck = (text: string) => text.startsWith('생성 실패') || text.includes('통과하지 못함');

const liveLink = (name: string) => h('a', { class: 'cg-live', href: `/#live=${encodeURIComponent(name)}` }, `▶ ${name}`);

const FACTORS: Record<string, Key> = { structure: 'factorStructure', work: 'factorWork', disposition: 'factorDisposition', event: 'factorEvent', other: 'factorOther' };
const factorName = (f: string | null | undefined) => (f ? (FACTORS[f] ? t(FACTORS[f]) : f) : t('factorNone'));

// Department dots: a calm set that reads on both themes.
const DEPT_COLORS = ['#41a1cf', '#e2604f', '#3f7f5a', '#c08a2b', '#8a6fc7', '#d07aa6', '#4f8f9f', '#8d8f8a'];

// ---- start screen ----
async function start() {
  const [drafts, settings] = await Promise.all([
    api<Listed[]>('/api/drafts').catch(() => null),
    api<Settings>('/api/settings').catch(() => null),
  ]);
  const choice = (icon: string, title: Key, desc: Key, onClick: () => void) => {
    const b = h('button', { type: 'button', class: 'cg-new' }, h('span', { class: 'cg-new-icon' }, icon),
      h('span', {}, h('b', {}, t(title)), h('small', {}, t(desc))));
    b.onclick = onClick;
    return b;
  };
  const scratch = choice('✦', 'fromScratch', 'fromScratchDesc', async () => {
    try {
      const d = await api<Draft>('/api/drafts', { method: 'POST', body: { mode: 'scratch' } });
      location.href = `/create.html?draft=${d.id}`;
    } catch (error) { toast([errorText(error)], 'bad'); }
  });
  const variant = choice('⎘', 'fromScenario', 'fromScenarioDesc', () => void pickSource());
  const rows = drafts === null ? [h('p', { class: 'hint warn' }, t('serverDown'))]
    : drafts.length === 0 ? [h('p', { class: 'hint' }, t('noDrafts'))]
      : drafts.map(d => h('a', { class: 'cg-draft', href: `/create.html?draft=${d.id}` },
        h('span', { class: 'cg-draft-main' }, h('b', {}, d.title || t('untitled')),
          h('small', {}, `${t(d.mode === 'variant' ? 'modeVariant' : 'modeScratch')} · ${when(d.updated)}`)),
        d.saved.length ? h('span', { class: 'st ok' }, t('savedTag')) : h('span', { class: 'st pause' }, t('draftTag'))));
  root.replaceChildren(h('div', { class: 'cg-start' },
    h('a', { class: 'cg-back', href: '/' }, `← ${t('menu')}`),
    h('header', {}, h('div', { class: 'kicker' }, t('createKicker')), h('h1', {}, t('create')),
      h('p', { class: 'cg-lede' }, t('createFlow'))),
    h('section', { class: 'cg-card' }, h('div', { class: 'label' }, t('newDraft')), h('div', { class: 'cg-news' }, scratch, variant),
      providerNote(settings)),
    h('section', { class: 'cg-card' }, h('div', { class: 'label' }, t('continueDraft')), h('div', { class: 'cg-drafts' }, ...rows))));
}

/** One line saying why sending is off, or null when it is on. */
function sendBlocked(settings: Settings | null): Key | null {
  if (!settings) return 'settingsUnread'; // fail closed: the page cannot tell whether a call would cost
  if (settings.provider !== 'openai') return 'needOpenai';
  if (!settings.openai_key) return 'needKey';
  return null;
}

function providerNote(settings: Settings | null): HTMLElement | null {
  const blocked = sendBlocked(settings);
  return blocked ? h('p', { class: 'hint warn' }, `${t(blocked)} `, h('a', { href: '/#settings' }, t('openSettings'))) : null;
}

async function pickSource() {
  let catalog: Scenario[];
  try { catalog = await api<Scenario[]>('/api/scenarios'); } catch (error) { toast([errorText(error)], 'bad'); return; }
  let picked = catalog[0];
  const scl = h('div', { class: 'scl' });
  const cards = catalog.map(sc => {
    const b = h('button', { type: 'button', class: `sc${sc === picked ? ' on' : ''}` }, h('b', {}, sc.name),
      h('small', {}, sc.research_question), sc.extends ? h('em', {}, `← ${sc.extends}`) : null);
    b.onclick = () => { picked = sc; scl.querySelectorAll('.sc').forEach(x => x.classList.toggle('on', x === b)); };
    b.ondblclick = () => void go();
    return b;
  });
  scl.append(...cards);
  const search = h('input', { class: 'search', placeholder: t('searchScenario') }) as HTMLInputElement;
  search.oninput = () => {
    const q = search.value.trim().toLowerCase();
    cards.forEach((c, i) => { c.hidden = !catalog[i].name.toLowerCase().includes(q); });
  };
  const back = h('button', { type: 'button' }, t('back'));
  const ok = h('button', { type: 'button', class: 'primary-btn' }, t('startVariant'));
  const note = h('p', { class: 'hint' }, t('variantNote'));
  const d = dialog(t('pickSource'), [search, scl, note], [back, ok]);
  scl.style.marginTop = '8px';
  back.onclick = () => d.close();
  const go = async () => {
    if (!picked) return;
    ok.disabled = true;
    try {
      const made = await api<Draft>('/api/drafts', { method: 'POST', body: { mode: 'variant', source: picked.name } });
      location.href = `/create.html?draft=${made.id}`;
    } catch (error) {
      ok.disabled = false;
      note.className = 'hint warn';
      note.textContent = errorText(error);
    }
  };
  ok.onclick = () => void go();
}

// ---- work screen ----
type Tab = 'org' | 'people' | 'work' | 'schedule' | 'experiment' | 'yaml';
const TABS: [Tab, Key][] = [['org', 'tabOrg'], ['people', 'tabPeople'], ['work', 'tabWork'], ['schedule', 'tabSchedule'],
  ['experiment', 'tabExperiment'], ['yaml', 'tabYaml']];

async function work(id: string) {
  let draft: Draft;
  try {
    draft = await api<Draft>(`/api/drafts/${encodeURIComponent(id)}`);
  } catch (error) {
    root.replaceChildren(h('div', { class: 'cg-start' }, h('a', { class: 'cg-back', href: '/create.html' }, `← ${t('draftList')}`),
      h('section', { class: 'cg-card' }, h('p', { class: 'hint warn' }, errorText(error)))));
    return;
  }
  const settings = await api<Settings>('/api/settings').catch(() => null);
  const blocked = sendBlocked(settings);
  let role: Role = 'baseline', tab: Tab = 'org', busy = false, saving = false; // one request at a time: a turn or a save
  let pending: { text: string; files: string[] } | null = null;
  let attached: Attachment[] = [];

  // frame
  const title = h('b', {});
  const mode = h('span', { class: 'cg-mode' });
  const bar = h('header', { class: 'cg-bar' }, h('a', { class: 'cg-back', href: '/' }, `← ${t('menu')}`),
    h('div', { class: 'cg-title' }, title, mode), h('a', { class: 'cg-back', href: '/create.html' }, t('draftList')));

  const log = h('div', { class: 'cg-log', 'aria-live': 'polite' });
  const chips = h('div', { class: 'cg-chips' });
  const input = h('textarea', { rows: '3', placeholder: t('askPlaceholder') }) as HTMLTextAreaElement;
  const picker = h('input', { type: 'file', accept: '.md,text/markdown', multiple: '', hidden: '' }) as HTMLInputElement;
  const attach = h('button', { type: 'button', class: 'cg-attach', title: t('attachHint') }, `📎 ${t('attachMd')}`);
  const send = h('button', { type: 'button', class: 'primary-btn cg-send' }, t('send'));
  const reason = h('div', { class: 'cg-reason' });
  // Sending is a paid call: say so by the Send button (model and per-message cap from the server).
  const cost = settings?.provider === 'openai' && settings.model_decide && settings.generation_token_cap
    ? h('div', { class: 'cg-cost' }, t('paidCall', { model: settings.model_decide, cap: settings.generation_token_cap.toLocaleString() }))
    : null;
  const chat = h('section', { class: 'cg-panel cg-chat' }, log,
    h('div', { class: 'cg-compose' }, chips, input, reason, h('div', { class: 'cg-compose-foot' }, attach, picker,
      h('span', { class: 'cg-keys' }, t('enterHint')), send), cost));

  const versions = h('div', { class: 'cg-versions' });
  const tabs = h('nav', { class: 'cg-tabs', role: 'tablist' });
  const body = h('div', { class: 'cg-pbody' });
  const status = h('div', { class: 'cg-status' });
  const savedLine = h('div', { class: 'cg-saved' });
  const save = h('button', { type: 'button', class: 'primary-btn cg-savebtn' }, t('saveDraft'));
  const saveWhy = h('span', { class: 'cg-why' });
  const preview = h('section', { class: 'cg-panel cg-preview' }, h('div', { class: 'cg-phead' }, versions, tabs), body,
    h('div', { class: 'cg-pfoot' }, status, h('div', { class: 'cg-saverow' }, savedLine, h('span', { class: 'spacer' }), saveWhy, save)));

  root.replaceChildren(h('div', { class: 'cg-work' }, bar, h('div', { class: 'cg-split' }, chat, preview)));

  for (const [key, label] of TABS) {
    const b = h('button', { type: 'button', role: 'tab', 'data-tab': key }, t(label));
    b.onclick = () => { tab = key; drawPreview(); };
    tabs.append(b);
  }

  // ---- chat ----
  const drawLog = () => {
    const lines = draft.messages.map(m => m.role === 'check'
      ? h('div', { class: `cg-msg check${failedCheck(m.text) ? ' bad' : ''}` }, `⚙ ${m.text}`)
      : h('div', { class: `cg-msg ${m.role}` }, h('div', { class: 'cg-bubble' }, m.text),
        m.role === 'ai' && m.tokens ? h('small', { class: 'cg-tokens' }, t('tokensN', { n: m.tokens.toLocaleString() })) : null));
    if (!lines.length && !pending) {
      lines.push(h('div', { class: 'cg-msg ai intro' }, h('div', { class: 'cg-bubble' },
        draft.mode === 'variant' ? t('introVariant', { source: draft.source ?? '' }) : t('introScratch'))));
    }
    if (pending) {
      lines.push(h('div', { class: 'cg-msg user' }, h('div', { class: 'cg-bubble' }, pending.text,
        ...pending.files.map(name => h('span', { class: 'cg-filetag' }, `📄 ${name}`)))));
      lines.push(h('div', { class: 'cg-msg ai' }, h('div', { class: 'cg-bubble cg-busy' }, t('generating'), h('span', { class: 'cg-dots' }))));
    }
    log.replaceChildren(...lines);
    log.scrollTop = log.scrollHeight;
  };

  const drawCompose = () => {
    chips.replaceChildren(...attached.map(f => {
      const x = h('button', { type: 'button', title: t('removeFile') }, '×');
      x.onclick = () => { attached = attached.filter(a => a !== f); drawCompose(); };
      x.disabled = busy;
      return h('span', { class: 'cg-chip' }, `📄 ${f.name}`, h('small', {}, `${Math.ceil(bytes(f.text) / 1000)} KB`), x);
    }));
    chips.hidden = !attached.length;
    input.disabled = busy;
    attach.disabled = busy;
    send.disabled = busy || saving || blocked !== null;
    reason.replaceChildren(...(blocked ? [`${t(blocked)} `, h('a', { href: '/#settings' }, t('openSettings'))] : []));
    reason.hidden = !blocked;
  };

  attach.onclick = () => picker.click();
  picker.onchange = async () => {
    for (const file of Array.from(picker.files ?? [])) {
      if (!/\.(md|markdown)$/i.test(file.name) && file.type !== 'text/markdown') {
        toast([t('onlyMd', { name: file.name })], 'bad');
        continue;
      }
      const text = await file.text();
      const others = attached.filter(a => a.name !== file.name);
      if (bytes(text) > EACH_LIMIT || others.reduce((n, a) => n + bytes(a.text), bytes(text)) > ALL_LIMIT) {
        toast([t('errAttachLimit')], 'bad');
        continue;
      }
      attached = [...others, { name: file.name, text }];
    }
    picker.value = '';
    drawCompose();
  };

  const submit = async () => {
    const text = input.value.trim();
    if (busy || saving || blocked || (!text && !attached.length)) return;
    busy = true;
    pending = { text, files: attached.map(f => f.name) };
    drawLog();
    drawCompose();
    drawFoot();
    try {
      const next = await api<Draft>(`/api/drafts/${draft.id}/messages`, { method: 'POST', body: { text, files: attached } });
      input.value = '';
      attached = [];
      show(next);
    } catch (error) {
      // The text and the files stay in the composer for a retry; they clear only on success.
      if (error instanceof ApiError && error.status === 502) {
        // The server kept the message, its files and a "생성 실패" line: show the stored draft.
        // Resending a file under the same name replaces it there rather than doubling it.
        try { show(await api<Draft>(`/api/drafts/${draft.id}`)); } catch { /* keep what is on screen */ }
      }
      toast([errorText(error)], 'bad');
    } finally {
      busy = false;
      pending = null;
      drawLog();
      drawCompose();
      drawFoot();
      input.focus();
    }
  };
  send.onclick = () => void submit();
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.keyCode !== 229) { // 229: a Korean IME still composing
      e.preventDefault();
      void submit();
    }
  });

  // ---- preview ----
  const current = () => draft.versions[role];
  const other = () => draft.versions[role === 'baseline' ? 'variant' : 'baseline'];

  const drawPreview = () => {
    const hasVariant = draft.versions.variant !== null;
    if (!hasVariant) role = 'baseline';
    versions.replaceChildren(...(hasVariant ? [segmented<Role>([['baseline', 'baseline'], ['variant', 'variantLabel']], role,
      v => { role = v; drawPreview(); })] : []));
    versions.hidden = !hasVariant;
    tabs.querySelectorAll<HTMLButtonElement>('button').forEach(b => {
      const on = b.dataset.tab === tab;
      b.classList.toggle('on', on);
      b.setAttribute('aria-selected', String(on));
    });
    const v = current();
    if (!v) {
      body.replaceChildren(h('div', { class: 'cg-empty' }, t(draft.mode === 'variant' ? 'noVersion' : 'noDraftYet')));
      return;
    }
    let content: Node[];
    try {
      content = { org: orgTab, people: peopleTab, work: workTab, schedule: scheduleTab, experiment: experimentTab, yaml: yamlTab }[tab](v);
    } catch {
      content = [h('div', { class: 'cg-empty' }, t('cannotDraw'))];
    }
    const errors = draft.checks[role];
    body.replaceChildren(...(errors?.length && tab !== 'yaml' ? [h('p', { class: 'hint warn cg-inline' }, t('drawnWithErrors'))] : []), ...content);
    body.scrollTop = 0;
  };

  const people = (v: Version) => list<Person>(v.company?.people);
  const nameOf = (v: Version) => {
    const names = new Map(people(v).map(p => [p.id, p.name || p.id] as const));
    return (id: string | null | undefined) => (id ? names.get(id) ?? id : '—');
  };
  const deptOf = (v: Version) => {
    const depts = list<{ id: string; name: string }>(v.company?.departments);
    return (id: string | null | undefined) => {
      const i = depts.findIndex(d => d.id === id);
      return { name: i >= 0 ? depts[i].name : id ?? '—', color: DEPT_COLORS[(i >= 0 ? i : depts.length) % DEPT_COLORS.length] };
    };
  };
  const dot = (color: string) => h('span', { class: 'cg-dot', style: `background:${color}` });
  const section = (label: string, ...children: (Node | null)[]) => h('section', { class: 'cg-sec' }, h('h3', {}, label), ...children);

  function orgTab(v: Version): Node[] {
    const all = people(v), ids = new Set(all.map(p => p.id)), dept = deptOf(v);
    const kids = new Map<string | null, Person[]>();
    for (const p of all) {
      const boss = p.reports_to && ids.has(p.reports_to) && p.reports_to !== p.id ? p.reports_to : null;
      kids.set(boss, [...(kids.get(boss) ?? []), p]);
    }
    const seen = new Set<string>();
    const tree = (boss: string | null): HTMLElement | null => {
      const under = (kids.get(boss) ?? []).filter(p => !seen.has(p.id));
      if (!under.length) return null;
      under.forEach(p => seen.add(p.id));
      return h('ul', { class: 'cg-tree' }, ...under.map(p => {
        const d = dept(p.department);
        return h('li', {}, h('div', { class: 'cg-node' }, dot(d.color), h('b', {}, p.name || p.id),
          h('span', {}, p.role ?? ''), h('small', {}, `${d.name}${p.position ? ` · ${p.position}` : ''} · ${p.id}`)), tree(p.id));
      }));
    };
    const top = tree(null);
    const loose = all.filter(p => !seen.has(p.id)); // a reports_to loop: shown flat rather than lost
    const legend = h('div', { class: 'cg-legend' }, ...list<{ id: string; name: string }>(v.company?.departments)
      .map(d => h('span', {}, dot(dept(d.id).color), d.name)));
    return [h('div', { class: 'cg-org-head' }, h('b', {}, v.company?.organization ?? ''), h('span', {}, v.company?.project ?? '')),
      legend, top ?? h('div', { class: 'cg-empty' }, t('noPeople')),
      loose.length ? section(t('orgLoop'), h('ul', { class: 'cg-tree' }, ...loose.map(p => h('li', {}, h('div', { class: 'cg-node' },
        dot(dept(p.department).color), h('b', {}, p.name || p.id), h('small', {}, `→ ${p.reports_to ?? ''}`)))))) : null]
      .filter((n): n is HTMLElement => n !== null);
  }

  function peopleTab(v: Version): Node[] {
    const dept = deptOf(v);
    const before = new Map(people(other() ?? v).map(p => [p.id, p] as const));
    const compare = role === 'variant' && draft.versions.baseline !== null;
    const trait = (p: Person, key: 'communication_style' | 'pressure_response' | 'conflict_engagement_style', label: Key) => {
      const changed = compare && (before.get(p.id)?.[key] ?? '') !== (p[key] ?? '');
      return [h('dt', {}, t(label)), h('dd', { class: changed ? 'cg-changed' : '' }, p[key] || '—',
        changed ? h('span', { class: 'cg-changed-tag' }, t('changed')) : null)];
    };
    return [h('div', { class: 'cg-people' }, ...people(v).map(p => {
      const d = dept(p.department);
      return h('article', { class: 'cg-person' },
        h('div', { class: 'cg-person-head' }, dot(d.color), h('b', {}, p.name || p.id), p.disc ? h('span', { class: 'cg-disc', title: 'DISC' }, p.disc) : null),
        h('div', { class: 'cg-person-sub' }, `${d.name} · ${p.role ?? ''}`),
        h('dl', {}, ...trait(p, 'communication_style', 'commStyle'), ...trait(p, 'pressure_response', 'pressureStyle'),
          ...trait(p, 'conflict_engagement_style', 'conflictStyle')));
    }))];
  }

  const span = (ticks: number) => t('effort', { n: ticks, min: ticks * 15 });
  const dueAt = (v: Version, tick: number) => {
    const s = v.scenario, perDay = s.ticks_per_day || 34, days = s.max_days || 1;
    const day = Math.min(Math.floor(tick / perDay), days - 1);
    return days > 1 ? t('dayAt', { day: day + 1, clock: hhmm(tick - day * perDay) }) : hhmm(tick);
  };
  const meta = (...parts: (string | Node | null | false)[]) =>
    h('div', { class: 'cg-meta' }, ...parts.filter((p): p is string | Node => !!p).flatMap((p, i) => (i ? [' · ', p] : [p])));

  function workTab(v: Version): Node[] {
    const s = v.scenario, name = nameOf(v), dept = deptOf(v);
    const runtime = new Map(list<{ id: string; effort_ticks: number; due: number }>(s.task_runtime).map(r => [r.id, r] as const));
    const unowned = new Set(list<string>(s.unassigned));
    const names = (ids: unknown) => list<string>(ids).map(name).join(', ');
    const core = list<Task>(v.company?.tasks).map(task => {
      const r = runtime.get(task.id);
      return h('li', { class: 'cg-item' }, h('div', { class: 'cg-item-head' }, h('span', { class: 'cg-id' }, task.id), h('b', {}, task.name),
        unowned.has(task.id) ? h('span', { class: 'st pause' }, t('unowned')) : null),
      meta(unowned.has(task.id) ? false : t('ownerIs', { name: name(task.owner) }), r ? span(r.effort_ticks) : false,
        r ? t('dueAt', { at: dueAt(v, r.due) }) : false,
        list(task.reviewers).length ? t('signOff', { names: names(task.reviewers) }) : t('noSignOff'),
        task.authority_scope ? h('span', { class: 'cg-tag' }, task.authority_scope) : null,
        list(task.predecessors).length ? t('after', { ids: list<string>(task.predecessors).join(', ') }) : false));
    });
    const projects = list<Project>(s.projects).map(p => h('li', { class: 'cg-item' },
      h('div', { class: 'cg-item-head' }, dot(dept(p.department).color), h('b', {}, p.name || p.id), h('span', { class: 'cg-id' }, p.id)),
      meta(dept(p.department).name, t('leadSigns', { name: name(p.lead) }), t('dueAt', { at: dueAt(v, p.due) }),
        list(p.start_after).length ? t('startsAfter', { ids: list<string>(p.start_after).join(', ') }) : false),
      h('ol', { class: 'cg-steps' }, ...list<Step>(p.steps).map(st => h('li', {}, h('span', {}, st.name),
        meta(span(st.effort_ticks), st.department ? t('crossPoint', { dept: dept(st.department).name }) : false,
          list(st.after).length ? t('after', { ids: list<string>(st.after).join(', ') }) : false))))));
    const extras = list<Extra>(s.extra_tasks);
    const arriving = extras.filter(x => x.arrives !== null && x.arrives !== undefined).sort((a, b) => (a.arrives ?? 0) - (b.arrives ?? 0));
    const routine = extras.filter(x => x.arrives === null || x.arrives === undefined);
    const extraRow = (x: Extra, arrives: boolean) => h('li', { class: 'cg-item' },
      h('div', { class: 'cg-item-head' }, arrives ? h('span', { class: 'cg-time' }, dueAt(v, x.arrives ?? 0)) : null, h('b', {}, x.name), h('span', { class: 'cg-id' }, x.id)),
      meta(arrives ? (x.assign_scope ? t('assignedBy', { scope: x.assign_scope }) : false) : t('ownerIs', { name: name(x.owner) }),
        span(x.effort_ticks), t('dueAt', { at: dueAt(v, x.due) }),
        list(x.reviewers).length ? t('signOff', { names: names(x.reviewers) }) : false));
    return [
      section(t('coreTasks', { n: core.length }), core.length ? h('ul', { class: 'cg-items' }, ...core) : h('div', { class: 'cg-empty' }, t('none'))),
      section(t('projectsN', { n: projects.length }), projects.length ? h('ul', { class: 'cg-items' }, ...projects) : h('div', { class: 'cg-empty' }, t('none'))),
      section(t('arrivingN', { n: arriving.length }), arriving.length ? h('ul', { class: 'cg-items' }, ...arriving.map(x => extraRow(x, true))) : h('div', { class: 'cg-empty' }, t('none'))),
      ...(routine.length ? [section(t('routineN', { n: routine.length }), h('ul', { class: 'cg-items' }, ...routine.map(x => extraRow(x, false))))] : []),
    ];
  }

  function scheduleTab(v: Version): Node[] {
    const s = v.scenario, name = nameOf(v);
    const who = (ids: unknown) => list<string>(ids).map(name).join(', ');
    interface Row { day: number; tick: number; ticks: number; kind: string; label: string; text: string; who: string }
    const rows: Row[] = [
      ...list<Meeting>(s.engine?.meetings).map(m => ({ day: m.day, tick: m.tick, ticks: m.duration_ticks, kind: 'meeting', label: t('meeting'),
        text: m.agenda, who: `${t('organizer', { name: name(m.organizer) })} · ${who(m.participants)}` })),
      ...list<Shock>(s.engine?.shocks).map(x => ({ day: x.day, tick: x.tick, ticks: 0, kind: 'shock', label: t('shock'),
        text: `${x.kind.replace(/_/g, ' ')}${x.task ? ` · ${x.task}` : ''}`, who: x.agent ? name(x.agent) : '' })),
      ...list<Block>(s.weekly_operations?.blocks).map(b => ({ day: b.day, tick: b.tick, ticks: b.duration_ticks, kind: 'block',
        label: BLOCKS[b.kind] ? t(BLOCKS[b.kind]) : b.kind, text: b.text, who: who(b.participants) })),
    ];
    if (s.weekly_operations) {
      const days = new Set([0, ...rows.map(r => r.day)]);
      for (const day of days) rows.push({ day, tick: s.weekly_operations.lunch_start_tick ?? 16, ticks: 4, kind: 'lunch', label: t('lunch'), text: '', who: '' });
    }
    rows.sort((a, b) => a.day - b.day || a.tick - b.tick);
    if (!rows.length) return [h('div', { class: 'cg-empty' }, t('noSchedule'))];
    const multi = new Set(rows.map(r => r.day)).size > 1 || (s.max_days ?? 1) > 1;
    const out: Node[] = [];
    let day = -1;
    for (const r of rows) {
      if (multi && r.day !== day) { day = r.day; out.push(h('h3', { class: 'cg-day' }, t('dayN', { n: day + 1 }))); }
      out.push(h('div', { class: `cg-slot ${r.kind}` },
        h('div', { class: 'cg-time' }, r.ticks ? `${hhmm(r.tick)}–${hhmm(r.tick + r.ticks)}` : hhmm(r.tick)),
        h('div', { class: 'cg-slot-body' }, h('span', { class: `cg-kind ${r.kind}` }, r.label), r.text ? h('span', { class: 'cg-slot-text' }, r.text) : null,
          r.who ? h('small', {}, r.who) : null)));
    }
    return [h('p', { class: 'hint cg-inline' }, t('clockRule')), ...out];
  }

  function experimentTab(v: Version): Node[] {
    const e = draft.experiment, s = v.scenario, name = nameOf(v);
    const subject = (x: string) => (x === 'all' ? t('everyone') : x.startsWith('partners_of:') ? t('partnersOf', { name: name(x.slice(12)) }) : name(x));
    const measure = (m: Measure) => h('li', {}, h('b', {}, METRICS[m.metric] ? t(METRICS[m.metric]) : m.metric), ` · ${subject(m.subject)}`,
      m.toward ? ` → ${name(m.toward)}` : '', h('span', { class: `cg-dir ${m.direction}` }, m.direction === 'up' ? ` ↑ ${t('goesUp')}` : ` ↓ ${t('goesDown')}`));
    const field = (label: Key, value: Node | string | null) => h('div', { class: 'cg-field' }, h('dt', {}, t(label)), h('dd', {}, value ?? '—'));
    const ul = (items: string[]) => (items.length ? h('ul', { class: 'cg-bullets' }, ...items.map(x => h('li', {}, x))) : '—');
    return [
      e ? section(t('experiment'), h('dl', { class: 'cg-fields' },
        field('experimentId', e.id || t('idOnSave')), field('thisRole', t(role === 'baseline' ? 'baseline' : 'variantLabel')),
        field('factor', factorName(e.factor ?? draft.factor)), field('hypothesis', e.hypothesis || null),
        field('measures', list<Measure>(e.measures).length ? h('ul', { class: 'cg-bullets' }, ...list<Measure>(e.measures).map(measure)) : null),
        field('behaviourChecks', ul(list<string>(e.behaviour_checks)))))
        : section(t('experiment'), h('div', { class: 'cg-empty' }, t('noExperiment'))),
      section(t('inScenario'), h('dl', { class: 'cg-fields' },
        field('researchQuestion', s.research_question || null), field('manipulated', s.manipulated_variable || null),
        field('fixedVars', list<string>(s.fixed_variables).length ? h('div', { class: 'cg-tags' }, ...list<string>(s.fixed_variables).map(x => h('span', { class: 'cg-tag' }, x))) : null),
        field('manipulationCheck', ul(list<string>(s.manipulation_check))))),
      section(t('materialsN', { n: draft.materials.length }), draft.materials.length
        ? h('ul', { class: 'cg-bullets' }, ...draft.materials.map(m => h('li', {}, `📄 ${m.name}`, h('small', {}, ` ${Math.ceil(bytes(m.text) / 1000)} KB`))))
        : h('div', { class: 'cg-empty' }, t('noMaterials'))),
    ];
  }

  function yamlTab(_v: Version): Node[] {
    const files = draft.files[role];
    if (!files) return [h('div', { class: 'cg-empty' }, t('yamlAfterPass'))];
    return [h('p', { class: 'hint cg-inline' }, t('yamlNote')), ...Object.entries(files).map(([path, text]) => {
      const copy = h('button', { type: 'button' }, t('copy'));
      copy.onclick = async () => {
        try { await navigator.clipboard.writeText(text); copy.textContent = t('copied'); } catch { copy.textContent = t('copyFailed'); }
        setTimeout(() => { copy.textContent = t('copy'); }, 1600);
      };
      return h('div', { class: 'cg-file' }, h('div', { class: 'cg-file-head' }, h('code', {}, path), copy), h('pre', {}, text));
    })];
  }

  // ---- checks, the pair's differences, save ----
  const saveBlock = (): Key | null => {
    const present = ROLES.filter(r => draft.versions[r] !== null);
    if (draft.mode === 'variant' && !draft.versions.variant) return 'errVariantFirst';
    if (!present.length) return 'errNothing';
    if (present.some(r => draft.checks[r]?.length !== 0)) return 'errFixFirst';
    return null;
  };

  const drawFoot = () => {
    const checks: Node[] = [];
    for (const r of ROLES) {
      const errors = draft.checks[r];
      if (errors === null || draft.versions[r] === null) continue;
      const label = t(r === 'baseline' ? 'baseline' : 'variantLabel');
      checks.push(errors.length
        ? h('details', { class: 'cg-check bad' }, h('summary', {}, `⚠ ${label} · ${t('errorsN', { n: errors.length })}`),
          h('ul', {}, ...errors.map(x => h('li', {}, x))))
        : h('div', { class: 'cg-check ok' }, `✓ ${label} · ${t('checkPass')}`));
    }
    if (!checks.length) checks.push(h('div', { class: 'cg-check' }, t('noChecksYet')));
    status.replaceChildren(h('div', { class: 'cg-checks' }, ...checks), ...(draft.versions.variant ? [diffLine()] : []));

    savedLine.replaceChildren(...(draft.saved.length ? [h('span', {}, t('savedAs')), ...draft.saved.map(liveLink)] : []));
    const why = saveBlock();
    save.disabled = why !== null || busy || saving;
    save.title = why ? t(why) : '';
    saveWhy.textContent = why ? t(why) : '';
  };

  const counts = (rows: Change[]) => {
    const by = new Map<string, number>();
    rows.forEach(r => by.set(r.factor, (by.get(r.factor) ?? 0) + 1));
    return [...by].map(([f, n]) => t('factorCount', { factor: factorName(f), n })).join(', ');
  };
  const changeList = (rows: Change[]) => h('ul', { class: 'cg-changes' }, ...rows.map(r => h('li', {},
    h('code', {}, r.path), h('span', { class: 'cg-factor' }, factorName(r.factor)),
    h('div', { class: 'cg-ab' }, h('span', { class: 'a' }, short(r.a)), ' → ', h('span', { class: 'b' }, short(r.b))))));

  function diffLine(): Node {
    const label = h('b', {}, t('diffTitle'));
    if (draft.checks.baseline?.length !== 0 || draft.checks.variant?.length !== 0) {
      return h('div', { class: 'cg-diff' }, label, ' ', t('diffNeedsPass'));
    }
    if (!draft.diff.length) return h('div', { class: 'cg-diff warn' }, label, ' ', t('diffNone'));
    const intended = t('intendedFactor', { factor: factorName(draft.factor) });
    if (!draft.outside.length) {
      return h('details', { class: 'cg-diff ok' }, h('summary', {}, label, ` ✓ ${counts(draft.diff)} · ${t('diffOnlyFactor')}`),
        h('div', { class: 'hint' }, intended), changeList(draft.diff));
    }
    const outsidePaths = new Set(draft.outside.map(r => r.path));
    const inside = draft.diff.filter(r => !outsidePaths.has(r.path));
    return h('details', { class: 'cg-diff warn', open: '' },
      h('summary', {}, label, ` ⚠ ${t('outsideN', { n: draft.outside.length })}${inside.length ? ` · ${t('insideAre', { list: counts(inside) })}` : ''}`),
      h('div', { class: 'hint' }, intended), changeList(draft.outside),
      inside.length ? h('details', {}, h('summary', {}, t('showInside', { n: inside.length })), changeList(inside)) : null);
  }

  const confirmOutside = () => new Promise<boolean>(resolve => {
    const no = h('button', { type: 'button' }, t('cancel'));
    const yes = h('button', { type: 'button', class: 'primary-btn' }, t('saveAnyway'));
    const d = dialog(t('outsideTitle'), [h('p', {}, t('outsideBody', { factor: factorName(draft.factor) })),
      h('div', { class: 'cg-dialog-list' }, changeList(draft.outside))], [no, yes]);
    let answer = false;
    no.onclick = () => d.close();
    yes.onclick = () => { answer = true; d.close(); };
    d.addEventListener('close', () => resolve(answer));
  });

  save.onclick = async () => {
    const accept = draft.outside.length ? await confirmOutside() : false;
    if ((draft.outside.length && !accept) || busy || saving) return;
    saving = true;
    save.disabled = true;
    drawCompose();
    try {
      const next = await api<Draft>(`/api/drafts/${draft.id}/save`, { method: 'POST', body: { accept_outside: accept } });
      show(next);
      const names = next.saved;
      toast([t('savedToast', { names: names.join(', ') }), ' ', ...(names.length ? [liveLink(names[names.length - 1])] : [])], 'ok');
    } catch (error) {
      toast([errorText(error)], 'bad');
    } finally {
      saving = false;
      drawFoot();
      drawCompose();
    }
  };

  // ---- one draft on screen ----
  function show(next: Draft) {
    const hadVariant = draft.versions.variant !== null;
    draft = next;
    if (!hadVariant && draft.versions.variant) role = 'variant'; // a new variant: show what just arrived
    title.textContent = draft.title || t('untitled');
    mode.textContent = draft.mode === 'variant' ? `${t('modeVariant')} · ${draft.source ?? ''}` : t('modeScratch');
    drawLog();
    drawPreview();
    drawFoot();
  }

  if (draft.versions.variant) role = 'variant'; // the pair's newer half, where the differences show
  show(draft);
  drawCompose();
  if (!blocked) input.focus();
}

const BLOCKS: Record<string, Key> = { preparation: 'blockPrep', external_meeting: 'blockExternal', transition: 'blockTransition', briefing: 'blockBriefing' };
const METRICS: Record<string, Key> = { stress: 'metricStress', mood: 'metricMood', relation: 'metricRelation', task_completion: 'metricTasks', rest_ratio: 'metricRest' };

const draftId = new URLSearchParams(location.search).get('draft');
void (draftId ? work(draftId) : start());
