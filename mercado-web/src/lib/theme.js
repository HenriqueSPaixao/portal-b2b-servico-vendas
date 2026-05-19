const KEY = 'theme';

export function applyInitialTheme() {
  const stored = localStorage.getItem(KEY);
  const theme = stored || 'dark';
  document.documentElement.classList.toggle('dark', theme === 'dark');
  return theme;
}

export function getTheme() {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

export function toggleTheme() {
  const next = getTheme() === 'dark' ? 'light' : 'dark';
  document.documentElement.classList.toggle('dark', next === 'dark');
  localStorage.setItem(KEY, next);
  return next;
}
