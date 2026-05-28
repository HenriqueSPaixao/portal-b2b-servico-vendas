export const MODO_COLORS = {
  direto: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
  leilao_direto: 'bg-purple-500/15 text-purple-600 dark:text-purple-400',
  leilao_reverso: 'bg-pink-500/15 text-pink-600 dark:text-pink-400',
};

export const STATUS_COLORS = {
  ABERTO: 'bg-brand-green/15 text-brand-green',
  FECHADA: 'bg-zinc-500/15 text-zinc-600 dark:text-zinc-400',
  CONCLUIDO: 'bg-zinc-500/15 text-zinc-600 dark:text-zinc-400',
  CANCELADO: 'bg-rose-500/15 text-rose-600 dark:text-rose-400',
};

export function truncate(s, n = 8) {
  if (!s) return '';
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

export function fmtDate(s) {
  if (!s) return '';
  try {
    return new Date(s).toLocaleString('pt-BR');
  } catch {
    return s;
  }
}
