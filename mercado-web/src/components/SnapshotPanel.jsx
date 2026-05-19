import { useState } from 'react';
import { MercadoApi } from '../api/client.js';

const UUID_RE = /^[0-9a-fA-F-]{32,36}$/;

export default function SnapshotPanel() {
  const [produtoId, setProdutoId] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setData(null);
    if (!UUID_RE.test(produtoId.trim())) {
      setError('UUID inválido.');
      return;
    }
    setLoading(true);
    try {
      const result = await MercadoApi.snapshot(produtoId.trim());
      setData(result);
    } catch (err) {
      const code = err.response?.status;
      if (code === 404) setError('Sem dados para este produto.');
      else if (code === 401) setError('JWT inválido ou expirado.');
      else setError(`Erro ${code || ''} ao consultar snapshot.`);
    } finally {
      setLoading(false);
    }
  }

  const oferta = data?.ofertas || data?.fornecimentos || [];
  const demanda = data?.demandas || data?.demanda || [];
  const totais = data
    ? { oferta: data.total_oferta, demanda: data.total_demanda }
    : null;

  return (
    <div className="card">
      <h2 className="font-semibold mb-3">Snapshot por produto</h2>
      <form onSubmit={handleSubmit} className="flex gap-2 mb-3">
        <input
          type="text"
          value={produtoId}
          onChange={(e) => setProdutoId(e.target.value)}
          placeholder="produto_id (UUID)"
          className="input font-mono text-xs"
          aria-label="UUID do produto"
        />
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? '…' : 'Buscar'}
        </button>
      </form>
      {error && (
        <p className="text-sm text-rose-600 dark:text-rose-400 mb-3">{error}</p>
      )}
      {data && (
        <>
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
