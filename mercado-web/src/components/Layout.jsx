import { useEffect, useState } from 'react';
import { getJwt } from '../lib/jwt-handshake.js';
import { getTheme, toggleTheme } from '../lib/theme.js';

export default function Layout({ children }) {
  const [theme, setTheme] = useState(getTheme());
  const [hasJwt, setHasJwt] = useState(Boolean(getJwt()));

  useEffect(() => {
    const onStorage = () => setHasJwt(Boolean(getJwt()));
    window.addEventListener('storage', onStorage);
    const interval = setInterval(onStorage, 2000);
    return () => {
      window.removeEventListener('storage', onStorage);
      clearInterval(interval);
    };
  }, []);

  function handleToggle() {
    setTheme(toggleTheme());
  }

  return (
    <div className="min-h-full">
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto max-w-7xl px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-md bg-brand-green flex items-center justify-center text-white font-bold">
              M
            </div>
            <div>
              <div className="font-semibold leading-tight">Mercado</div>
              <div className="text-xs text-zinc-500 dark:text-zinc-400 leading-tight">
                Matching Engine — Portal B2B
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {hasJwt ? (
              <span className="chip-ok">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-green" /> Sessão ativa
              </span>
            ) : (
              <span className="chip-warn">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" /> Sessão expirada
              </span>
            )}
            <button
              type="button"
              onClick={handleToggle}
              aria-label="Alternar tema"
              className="btn-ghost"
            >
              {theme === 'dark' ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
