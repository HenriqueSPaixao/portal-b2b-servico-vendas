import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { NegociacaoApi } from '../api/client.js';
import { getJwt } from '../lib/jwt-handshake.js';
import { MODO_COLORS, STATUS_COLORS, truncate, fmtDate, fmtBRL } from '../lib/format.js';
import MeusLeiloes from './MeusLeiloes.jsx';

function Badge({ map, value }) {
  const cls = map[value] || 'bg-zinc-500/15 text-zinc-600 dark:text-zinc-400';
  return <span className={`chip ${cls}`}>{value}</span>;
}

export default function ProcessosList() {
  const navigate = useNavigate();
  const [status, setStatus] = useState('');
  const [modo, setModo] = useState('');
  const [produtoNome, setProdutoNome] = useState('');
  const [produtos, setProdutos] = useState([]);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const lastQuery = useRef({});

  // Lista de produtos para autocomplete por nome (alimentada pelo ProdutoCache).
  async function loadProdutos() {
    try {
      const list = await NegociacaoApi.listarProdutos();
      setProdutos(Array.isArray(list) ? list : []);
    } catch {
      // silencioso: autocomplete fica vazio mas o resto da tela continua usável
    }
  }

  useEffect(() => {
    loadProdutos();
  }, []);

  function findProdutoIdByNome(nome) {
    const alvo = (nome || '').trim().toLowerCase();
    if (!alvo) return null;
    const match = produtos.find((p) => (p.nome || '').toLowerCase() === alvo);
    return match ? match.produto_id : null;
  }

  const query = useMemo(() => {
    const q = { limit: 100 };
    if (status) q.status = status;
    if (modo) q.modo = modo;
    const produtoId = findProdutoIdByNome(produtoNome);
    if (produtoId) q.produto_id = produtoId;
    return q;
  }, [status, modo, produtoNome, produtos]);

  useEffect(() => {
    let alive = true;
    let id;
    async function load() {
      if (!getJwt()) {
        setError('jwt');
        setLoading(false);
        return;
      }
      try {
        const data = await NegociacaoApi.listarProcessos(query);
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
    lastQuery.current = query;
    const t = setTimeout(load, 400);
    id = setInterval(load, 5000);
    return () => {
      alive = false;
      clearTimeout(t);
      clearInterval(id);
    };
  }, [query]);

  return (
    <>
      <MeusLeiloes />
      <div className="card mb-5">
        <h2 className="font-semibold mb-3">Filtros</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="label" htmlFor="f-status">Status</label>
            <select id="f-status" className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Todos</option>
              <option value="ABERTO">Aberto</option>
              <option value="FECHADA">Fechado</option>
              <option value="CONCLUIDO">Concluído</option>
              <option value="CANCELADO">Cancelado</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="f-modo">Modo</label>
            <select id="f-modo" className="input" value={modo} onChange={(e) => setModo(e.target.value)}>
              <option value="">Todos</option>
              <option value="direto">Venda direta</option>
              <option value="leilao_direto">Leilão direto</option>
              <option value="leilao_reverso">Leilão reverso</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="f-produto">Produto</label>
            <input
              id="f-produto"
              className="input"
              placeholder="Nome do produto"
              value={produtoNome}
              onChange={(e) => setProdutoNome(e.target.value)}
              list="produtos-list-neg"
              autoComplete="off"
            />
            <datalist id="produtos-list-neg">
              {produtos.map((p) => (
                <option
                  key={p.produto_id}
                  value={p.nome || ''}
                  label={p.codigo ? `código ${p.codigo}` : undefined}
                />
              ))}
            </datalist>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Processos</h2>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">atualiza a cada 5s</span>
        </div>
        {error === 'jwt' && (
          <p className="text-sm text-amber-600 dark:text-amber-400">
            Sessão expirada. Acesse novamente pelo portal para continuar.
          </p>
        )}
        {error === 'fetch' && (
          <p className="text-sm text-rose-600 dark:text-rose-400">
            Não foi possível carregar os processos no momento. Tente novamente em alguns segundos.
          </p>
        )}
        {!error && loading && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Carregando…</p>
        )}
        {!error && !loading && items.length === 0 && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Nenhum processo encontrado com esses filtros.
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
                  <th className="px-5 py-2 text-right">V. reserva</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {items.map((p) => (
                  <tr
                    key={p.id}
                    onClick={() => navigate(`/processos/${p.id}`)}
                    className="cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                  >
                    <td className="px-5 py-2"><Badge map={MODO_COLORS} value={p.modo} /></td>
                    <td className="px-5 py-2" title={p.produto_id}>
                      {p.produto_nome ? (
                        <span>{p.produto_nome}</span>
                      ) : (
                        <span className="font-mono text-xs">{truncate(p.produto_id)}</span>
                      )}
                    </td>
                    <td className="px-5 py-2"><Badge map={STATUS_COLORS} value={p.status} /></td>
                    <td className="px-5 py-2">{fmtDate(p.data_inicio)}</td>
                    <td className="px-5 py-2">{fmtDate(p.data_fim)}</td>
                    <td className="px-5 py-2 text-right font-mono">{fmtBRL(p.valor_reserva)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
