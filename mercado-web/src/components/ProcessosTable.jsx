import { useEffect, useState } from 'react';
import { MercadoApi } from '../api/client.js';
import { getJwt } from '../lib/jwt-handshake.js';

const MODO_COLORS = {
  direto: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
  leilao_direto: 'bg-purple-500/15 text-purple-600 dark:text-purple-400',
  leilao_reverso: 'bg-pink-500/15 text-pink-600 dark:text-pink-400',
};

function ModoBadge({ modo }) {
  const cls = MODO_COLORS[modo] || 'bg-zinc-500/15 text-zinc-600 dark:text-zinc-400';
  return <span className={`chip ${cls}`}>{modo}</span>;
}

function truncate(s, n = 8) {
  if (!s) return '';
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

function fmtDate(s) {
  if (!s) return '';
  try {
    return new Date(s).toLocaleString('pt-BR');
  } catch {
    return s;
  }
}

export default function ProcessosTable() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    async function load() {
      if (!getJwt()) {
        setError('jwt');
        setLoading(false);
        return;
      }
      try {
        const data = await MercadoApi.listarProcessos();
        if (!alive) return;
        setItems(Array.isArray(data) ? data : []);
        setError(null);
      } catch (err) {
        if (!alive) return;
        setError(err.response?.status === 401 ? 'jwt' : 'fetch');
      } finally {
        if (alive) setLoading(false);
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">Processos disparados pelo matching</h2>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          atualiza a cada 5s
        </span>
      </div>
      {error === 'jwt' && (
        <p className="text-sm text-amber-600 dark:text-amber-400">
          Sem JWT. Abra com <code>?jwt=…</code> ou rode <code>python scripts/gen_jwt.py</code>.
        </p>
      )}
      {error === 'fetch' && (
        <p className="text-sm text-rose-600 dark:text-rose-400">
          Erro ao consultar o mercado-service. Está rodando em {import.meta.env.VITE_API_BASE || 'http://localhost:5005'}?
        </p>
      )}
      {!error && loading && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Carregando…</p>
      )}
      {!error && !loading && items.length === 0 && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Nenhum matching disparado ainda. Publique <code>fornecimento_criado</code> + <code>demanda_criada</code> ou rode <code>./scripts/run_smoke.sh</code>.
        </p>
      )}
      {!error && items.length > 0 && (
        <div className="overflow-x-auto -mx-5">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              <tr>
                <th className="px-5 py-2">Modo</th>
                <th className="px-5 py-2">Produto</th>
                <th className="px-5 py-2">Status</th>
                <th className="px-5 py-2">Início</th>
                <th className="px-5 py-2">Fim</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {items.map((p, i) => (
                <tr key={p.processo_id || p.id || i}>
                  <td className="px-5 py-2"><ModoBadge modo={p.modo} /></td>
                  <td className="px-5 py-2" title={p.produto_id}>
                    {p.produto_nome ? (
                      <span>{p.produto_nome}</span>
                    ) : (
                      <span className="font-mono text-xs">{truncate(p.produto_id)}</span>
                    )}
                  </td>
                  <td className="px-5 py-2">{p.status || '—'}</td>
                  <td className="px-5 py-2">{fmtDate(p.data_inicio)}</td>
                  <td className="px-5 py-2">{fmtDate(p.data_fim)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
