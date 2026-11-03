// Per-viewer conveniences kept in this browser: the UI language and the colour theme.
export type Lang = 'ko' | 'en';
export type Theme = 'light' | 'dark' | 'system';

const read = (key: string): string | null => {
  try { return localStorage.getItem(key); } catch { return null; }
};
const write = (key: string, value: string) => {
  try { localStorage.setItem(key, value); } catch { /* private mode: this visit only */ }
};

export const getLang = (): Lang => (read('cd.lang') === 'en' ? 'en' : 'ko');
export const setLang = (lang: Lang) => write('cd.lang', lang);
export const getTheme = (): Theme => {
  const theme = read('cd.theme');
  return theme === 'light' || theme === 'dark' ? theme : 'system';
};
export function setTheme(theme: Theme) {
  write('cd.theme', theme);
  applyTheme();
}

const dark = matchMedia('(prefers-color-scheme: dark)');
export function applyTheme() {
  const theme = getTheme();
  document.documentElement.dataset.theme = theme === 'system' ? (dark.matches ? 'dark' : 'light') : theme;
}
dark.addEventListener('change', applyTheme);
