import { useEffect, useState } from 'react';
import { MercadoApi } from '../api/client.js';

export default function SnapshotPanel() {
  const [produtos, setProdutos] = useState([]);
  const [nomeBusca, setNomeBusca] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function loadProdutos() {
    try {
      const list = await MercadoApi.listarProdutos();
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

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setData(null);
    const produtoId = findProdutoIdByNome(nomeBusca);
    if (!produtoId) {
      setError(
        'Produto não encontrado. Digite o nome exato como aparece na lista de sugestões.'
      );
      return;
    }
    setLoading(true);
    try {
      const result = await MercadoApi.snapshot(produtoId);
      setData(result);
    } catch (err) {
      const code = err.response?.status;
      if (code === 404) setError('Ainda não temos dados de oferta ou demanda para este produto.');
      else if (code === 401) setError('Sessão expirada. Acesse novamente pelo portal para continuar.');
      else setError('Não foi possível consultar este produto no momento. Tente novamente em alguns segundos.');
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

  const totalFornecedores = new Set(
    oferta.map((o) => o.empresa_fornecedor_id).filter(Boolean)
  ).size;
  const totalCompradores = new Set(
    demanda.map((d) => d.empresa_comprador_id).filter(Boolean)
  ).size;

  return (
    <div className="card">
      <h2 className="font-semibold mb-3">Oferta e demanda por produto</h2>
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
          Nenhum produto disponível ainda. Aguarde alguns instantes e tente novamente.
        </p>
      )}
      {error && (
        <p className="text-sm text-rose-600 dark:text-rose-400 mb-3">{error}</p>
      )}
      {data && (
        <>
          {produtoInfo && (
            <div className="mb-4">
              <div className="font-semibold text-base">{produtoInfo.nome}</div>
              {produtoInfo.codigo && (
                <div className="text-xs text-zinc-500 dark:text-zinc-400">
                  Código <span className="font-mono">{produtoInfo.codigo}</span>
                </div>
              )}
            </div>
          )}
          {totais && (
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="rounded-md bg-brand-green/10 p-3 text-center">
                <div className="text-xs text-zinc-500 dark:text-zinc-400">Oferta total</div>
                <div className="font-mono font-semibold text-lg text-brand-green">{totais.oferta ?? '—'}</div>
                <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                  {totalFornecedores === 1
                    ? '1 fornecedor disponível'
                    : `${totalFornecedores} fornecedores disponíveis`}
                </div>
              </div>
              <div className="rounded-md bg-amber-500/10 p-3 text-center">
                <div className="text-xs text-zinc-500 dark:text-zinc-400">Demanda total</div>
                <div className="font-mono font-semibold text-lg text-amber-600 dark:text-amber-400">{totais.demanda ?? '—'}</div>
                <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                  {totalCompradores === 1
                    ? '1 comprador interessado'
                    : `${totalCompradores} compradores interessados`}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
