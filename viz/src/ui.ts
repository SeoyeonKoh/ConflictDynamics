// Small helpers the menu page and the scenario generator page share: the server call, the element
// builder, the dialog frame and the segmented switch.
import { t, type Key } from './i18n';

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
