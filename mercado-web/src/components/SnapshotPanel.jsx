import { useEffect, useState } from 'react';
import { MercadoApi } from '../api/client.js';

export default function SnapshotPanel() {
  const [produtos, setProdutos] = useState([]);
  const [nomeBusca, setNomeBusca] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // Carrega a lista de produtos uma vez ao montar; recarrega ao concluir busca
  // para captar produtos novos que chegaram via Kafka enquanto o usuário usa.
  async function loadProdutos() {
    try {
      const list = await MercadoApi.listarProdutos();
      setProdutos(Array.isArray(list) ? list : []);
    } catch {
      // silencioso: se /produtos falhar, o autocomplete fica vazio mas o
      // restante da tela continua usável.
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

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setData(null);
    const produtoId = findProdutoIdByNome(nomeBusca);
    if (!produtoId) {
      setError(
        'Produto não encontrado nos eventos do Kafka. Aguarde a Eq. Produtos publicar `produto_cadastrado` para este produto.'
      );
      return;
    }
    setLoading(true);
    try {
      const result = await MercadoApi.snapshot(produtoId);
      setData(result);
    } catch (err) {
      const code = err.response?.status;
      if (code === 404) setError('Sem dados para este produto.');
      else if (code === 401) setError('JWT inválido ou expirado.');
      else setError(`Erro ${code || ''} ao consultar snapshot.`);
    } finally {
      setLoading(false);
      loadProdutos();
    }
  }

  const oferta = data?.ofertas || data?.fornecimentos || [];
  const demanda = data?.demandas || data?.demanda || [];
  const totais = data
    ? { oferta: data.total_oferta, demanda: data.total_demanda }
    : null;
  const produtoInfo = data?.produto || null;

  return (
    <div className="card">
      <h2 className="font-semibold mb-3">Snapshot por produto</h2>
      <form onSubmit={handleSubmit} className="flex gap-2 mb-3">
        <input
          type="text"
          value={nomeBusca}
          onChange={(e) => setNomeBusca(e.target.value)}
          placeholder="Nome do produto"
          className="input"
          list="produtos-list"
          aria-label="Nome do produto"
          autoComplete="off"
        />
        <datalist id="produtos-list">
          {produtos.map((p) => (
            <option
              key={p.produto_id}
              value={p.nome || ''}
              label={p.codigo ? `código ${p.codigo}` : undefined}
            />
          ))}
        </datalist>
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? '…' : 'Buscar'}
        </button>
      </form>
      {produtos.length === 0 && !error && (
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">
          Nenhum produto conhecido ainda. Aguardando eventos <code>produto_cadastrado</code> do Kafka.
        </p>
      )}
      {error && (
        <p className="text-sm text-rose-600 dark:text-rose-400 mb-3">{error}</p>
      )}
      {data && (
        <>
          {produtoInfo && (
            <div className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">
              <span className="font-semibold text-zinc-700 dark:text-zinc-200">{produtoInfo.nome}</span>
              {produtoInfo.codigo && <> · código <code>{produtoInfo.codigo}</code></>}
              <> · <span className="font-mono">{produtoInfo.id}</span></>
            </div>
          )}
          {totais && (
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div className="rounded-md bg-brand-green/10 p-2 text-center">
                <div className="text-xs text-zinc-500 dark:text-zinc-400">Total oferta</div>
                <div className="font-mono font-semibold text-brand-green">{totais.oferta ?? '—'}</div>
              </div>
              <div className="rounded-md bg-amber-500/10 p-2 text-center">
                <div className="text-xs text-zinc-500 dark:text-zinc-400">Total demanda</div>
                <div className="font-mono font-semibold text-amber-600 dark:text-amber-400">{totais.demanda ?? '—'}</div>
              </div>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="rounded-md border border-zinc-200 dark:border-zinc-800 p-3">
              <div className="font-medium mb-1 text-brand-green">Ofertas ({oferta.length})</div>
              <pre className="overflow-x-auto whitespace-pre-wrap break-all">
                {JSON.stringify(oferta, null, 2)}
              </pre>
            </div>
            <div className="rounded-md border border-zinc-200 dark:border-zinc-800 p-3">
              <div className="font-medium mb-1 text-amber-600 dark:text-amber-400">Demandas ({demanda.length})</div>
              <pre className="overflow-x-auto whitespace-pre-wrap break-all">
                {JSON.stringify(demanda, null, 2)}
              </pre>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
