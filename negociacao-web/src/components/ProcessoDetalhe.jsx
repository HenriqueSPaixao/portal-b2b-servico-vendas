import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { NegociacaoApi } from '../api/client.js';
import { getJwt } from '../lib/jwt-handshake.js';
import { MODO_COLORS, STATUS_COLORS, fmtDate } from '../lib/format.js';
import LancesTable from './LancesTable.jsx';
import LanceForm from './LanceForm.jsx';

function Badge({ map, value }) {
  const cls = map[value] || 'bg-zinc-500/15 text-zinc-600 dark:text-zinc-400';
  return <span className={`chip ${cls}`}>{value}</span>;
}

function InfoRow({ label, children }) {
  return (
    <div>
      <div className="text-xs text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="text-sm break-all">{children}</div>
    </div>
  );
}

export default function ProcessoDetalhe() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [processo, setProcesso] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [closing, setClosing] = useState(false);

  const load = useCallback(async () => {
    if (!getJwt()) {
      setError('jwt');
      setLoading(false);
      return;
    }
    try {
      const data = await NegociacaoApi.detalhe(id);
      setProcesso(data);
      setError(null);
    } catch (err) {
      const code = err.response?.status;
      if (code === 404) setError('notfound');
      else if (code === 401) setError('jwt');
      else setError('fetch');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  async function handleFechar() {
    if (!window.confirm('Fechar este processo agora? Esta ação publica negociacao_fechada e não pode ser desfeita.')) {
      return;
    }
    setClosing(true);
    try {
      await NegociacaoApi.fechar(id);
      await load();
    } catch (err) {
      alert(`Erro ao fechar: ${err.response?.status || ''} ${err.response?.data?.detail || ''}`);
    } finally {
      setClosing(false);
    }
  }

  return (
    <>
      <div className="mb-4">
        <Link to="/" className="btn-ghost">← Voltar</Link>
      </div>

      {error === 'jwt' && (
        <div className="card">
          <p className="text-sm text-amber-600 dark:text-amber-400">
            Sem JWT. Abra com <code>?jwt=…</code> ou rode <code>python scripts/gen_jwt.py</code>.
          </p>
        </div>
      )}
      {error === 'notfound' && (
        <div className="card">
          <p className="text-sm text-rose-600 dark:text-rose-400">Processo não encontrado.</p>
        </div>
      )}
      {error === 'fetch' && (
        <div className="card">
          <p className="text-sm text-rose-600 dark:text-rose-400">
            Erro ao carregar processo.
          </p>
        </div>
      )}

      {!error && loading && !processo && (
        <div className="card">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Carregando…</p>
        </div>
      )}

      {!error && processo && (
        <div className="space-y-5">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold">Processo</h2>
              <div className="flex gap-2">
                <Badge map={MODO_COLORS} value={processo.modo} />
                <Badge map={STATUS_COLORS} value={processo.status} />
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <InfoRow label="ID"><span className="font-mono text-xs">{processo.id}</span></InfoRow>
              <InfoRow label="Produto"><span className="font-mono text-xs">{processo.produto_id}</span></InfoRow>
              <InfoRow label="Início">{fmtDate(processo.data_inicio)}</InfoRow>
              <InfoRow label="Fim">{fmtDate(processo.data_fim)}</InfoRow>
              <InfoRow label="Valor reserva"><span className="font-mono">{processo.valor_reserva ?? '—'}</span></InfoRow>
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold">Lances</h2>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                {processo.lances?.length || 0} no total
              </span>
            </div>
            <LancesTable lances={processo.lances || []} />
          </div>

          {processo.status === 'ABERTO' && (
            <div className="card">
              <h2 className="font-semibold mb-3">Registrar lance</h2>
              <LanceForm processoId={processo.id} onSuccess={load} />
            </div>
          )}

          {processo.status === 'ABERTO' && (
            <div className="card">
              <h2 className="font-semibold mb-1">Fechamento manual (admin)</h2>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">
                Encerra o processo agora e publica <code>negociacao_fechada</code>.
              </p>
              <button type="button" className="btn-danger" disabled={closing} onClick={handleFechar}>
                {closing ? 'Fechando…' : 'Fechar processo'}
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
