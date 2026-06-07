import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { NegociacaoApi } from '../api/client.js';
import { getJwt } from '../lib/jwt-handshake.js';
import { MODO_COLORS, STATUS_COLORS, fmtDate } from '../lib/format.js';
import LancesChat from './LancesChat.jsx';
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
    if (!window.confirm('Encerrar agora (ação de operador)? O leilão fecharia sozinho no fim do tempo. Não pode ser desfeito.')) {
      return;
    }
    setClosing(true);
    try {
      await NegociacaoApi.fechar(id);
      await load();
    } catch (err) {
      const detalhe = err.response?.data?.detail;
      alert(
        typeof detalhe === 'string' && detalhe
          ? `Não foi possível encerrar: ${detalhe}`
          : 'Não foi possível encerrar o processo no momento.'
      );
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
            Sessão expirada. Acesse novamente pelo portal para continuar.
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
            Não foi possível carregar este processo no momento. Tente novamente em alguns segundos.
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
              <InfoRow label="Produto">
                {processo.produto_nome ? (
                  <span title={processo.produto_id}>{processo.produto_nome}</span>
                ) : (
                  <span className="font-mono text-xs" title={processo.produto_id}>
                    sem nome (aguardando produto_cadastrado)
                  </span>
                )}
              </InfoRow>
              <InfoRow label="Início">{fmtDate(processo.data_inicio)}</InfoRow>
              <InfoRow label="Fim">{fmtDate(processo.data_fim)}</InfoRow>
              <InfoRow label="Valor reserva"><span className="font-mono">{processo.valor_reserva ?? '—'}</span></InfoRow>
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold">Negociação — fornecedor e comprador</h2>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                {processo.lances?.length || 0} lance(s) · atualiza a cada 5s
              </span>
            </div>
            <LancesChat lances={processo.lances || []} />
          </div>

          {processo.status === 'ABERTO' && (
            <div className="card">
              <h2 className="font-semibold mb-3">Registrar lance</h2>
              <LanceForm processoId={processo.id} onSuccess={load} />
            </div>
          )}

          {processo.status === 'ABERTO' && (
            <div className="card">
              <h2 className="font-semibold mb-1">Encerrar (operador)</h2>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">
                O leilão encerra <strong>sozinho</strong> no horário de término ({fmtDate(processo.data_fim)}).
                Este botão é um atalho de <strong>operador/admin</strong> para encerrar na hora — não é
                uma ação do comprador.
              </p>
              <button
                type="button"
                className="btn-danger"
                disabled={closing}
                onClick={handleFechar}
                title="Ação de operador/admin. O encerramento normal é automático, pelo tempo do leilão."
              >
                {closing ? 'Encerrando…' : 'Encerrar agora (operador)'}
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
