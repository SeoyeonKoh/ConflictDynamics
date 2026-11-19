// Small helpers the menu page and the scenario generator page share: the server call, the element
// builder, the dialog frame and the segmented switch.
import { t, type Key } from './i18n';
import { getLang, setLang, type Lang } from './prefs';

/** A refused call: the server's `{error}` as the message, with the HTTP status beside it. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

export async function api<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const response = await fetch(path, {
    method: init?.method ?? 'GET',
    headers: init?.body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError((data as { error?: string }).error ?? `${response.status}`, response.status);
  return data as T;
}

export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K, attrs: Record<string, string> = {}, ...children: (Node | string | null | undefined)[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') el.className = v; else el.setAttribute(k, v);
  }
  for (const c of children) if (c !== null && c !== undefined) el.append(c); // a malformed draft's missing field draws nothing
  return el;
}

export function dialog(title: string, body: (Node | null)[], foot: Node[], wide = false): HTMLDialogElement {
  const close = h('button', { class: 'x', title: t('close') }, '×');
  const d = h('dialog', { class: `panel${wide ? ' wide' : ''}` },
    h('div', { class: 'd-head' }, h('h1', {}, title), close), ...body.filter((n): n is Node => n !== null),
    h('div', { class: 'd-foot' }, ...foot));
  close.onclick = () => d.close();
  d.addEventListener('click', e => { if (e.target === d) d.close(); }); // a click on the backdrop
  d.addEventListener('close', () => d.remove());
  document.body.append(d);
  d.tabIndex = -1;
  d.showModal();
  d.focus(); // Tab reaches the controls from the top; no ring on the close button
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

// ---- Top-left page nav: the view's glass capsule (#bar .pill.nav), with labels beside the glyphs ----
const glyph = (d: string) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
export const ICONS = {
  home: glyph('<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h5v-6h4v6h5V9.5"/>'),
  replay: glyph('<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="m10 9 5 3-5 3z"/>'),
  live: glyph('<circle cx="12" cy="12" r="2"/><path d="M16.2 7.8a6 6 0 0 1 0 8.4M7.8 16.2a6 6 0 0 1 0-8.4M19 5a10 10 0 0 1 0 14M5 19A10 10 0 0 1 5 5"/>'),
  download: glyph('<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>'),
  copy: glyph('<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>'),
  check: glyph('<path d="m5 12.5 4.5 4.5L19 7"/>'),
  list: glyph('<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>'),
};

/** A glass capsule of icon+label links, divided like the view's nav. */
export function navPill(links: { href: string; icon: string; label: string }[]): HTMLElement {
  const nav = h('nav', { class: 'glass pill nav-pill' });
  links.forEach((l, i) => {
    if (i) nav.append(h('span', { class: 'nav-divider' }));
    const a = h('a', { class: 'nav-link', href: l.href }, h('span', { class: 'nav-ico', 'aria-hidden': 'true' }), h('span', {}, l.label));
    a.firstElementChild!.innerHTML = l.icon;
    nav.append(a);
  });
  return nav;
}

/** The 한국어 | English switch, each language by its own name, as the menu shows them. */
export function langSwitch(onChange: (lang: Lang) => void): HTMLElement {
  const lang = segmented<Lang>([['ko', 'uiLang'], ['en', 'uiLang']], getLang(), v => { setLang(v); onChange(v); });
  lang.querySelectorAll('button')[0].textContent = '한국어';
  lang.querySelectorAll('button')[1].textContent = 'English';
  return lang;
}
