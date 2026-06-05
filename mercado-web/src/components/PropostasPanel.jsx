import { useCallback, useEffect, useState } from 'react';
import { MercadoApi } from '../api/client.js';
import { getJwt } from '../lib/jwt-handshake.js';

function fmtDate(s) {
  if (!s) return '';
  try {
    return new Date(s).toLocaleString('pt-BR');
  } catch {
    return s;
  }
}

function ProdutoLabel({ nome, id }) {
  if (nome) return <span>{nome}</span>;
  return <span className="font-mono text-xs" title={id}>{id?.slice(0, 8)}…</span>;
}

/**
 * Mercado voltado ao fornecedor: lista os leilões diretos que estão esperando
 * a decisão dele ("o fornecedor manda no mercado"). Abrir → publica o leilão;
 * Recusar → fecha dentro do mercado, sem acionar nenhuma outra equipe.
 */
export default function PropostasPanel() {
  const [pendentes, setPendentes] = useState([]);
  const [log, setLog] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null); // processo_id em ação

  const load = useCallback(async () => {
    if (!getJwt()) {
      setError('jwt');
      setLoading(false);
      return;
    }
    try {
      const [props, decisoes] = await Promise.all([
        MercadoApi.listarPropostas(),
        MercadoApi.logDecisoes(),
      ]);
      setPendentes(Array.isArray(props) ? props : []);
      setLog(Array.isArray(decisoes) ? decisoes : []);
      setError(null);
    } catch (err) {
      setError(err.response?.status === 401 ? 'jwt' : 'fetch');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    const run = () => alive && load();
    run();
    const id = setInterval(run, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [load]);

  async function decidir(processoId, decisao) {
    setBusy(processoId);
    try {
      await MercadoApi.confirmarProposta(processoId, decisao);
      await load();
    } catch {
      setError('fetch');
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">Leilões aguardando você</h2>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">atualiza a cada 5s</span>
      </div>
      <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-4">
        Você é o fornecedor dono da oferta. Confirme se quer abrir o leilão para os
        compradores competirem — nada acontece até a sua decisão.
      </p>

      {error === 'jwt' && (
        <p className="text-sm text-amber-600 dark:text-amber-400">
          Sessão expirada. Acesse novamente pelo portal para continuar.
        </p>
      )}
      {error === 'fetch' && (
        <p className="text-sm text-rose-600 dark:text-rose-400">
          Não foi possível carregar agora. Tente novamente em alguns segundos.
        </p>
      )}
      {!error && loading && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Carregando…</p>
      )}
      {!error && !loading && pendentes.length === 0 && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Nenhum leilão aguardando decisão. Quando a procura por um produto seu superar
          a oferta, o convite para abrir o leilão aparece aqui.
        </p>
      )}

      {!error && pendentes.length > 0 && (
        <ul className="space-y-3">
          {pendentes.map((p) => (
            <li
              key={p.processo_id}
              className="rounded-md border border-zinc-200 dark:border-zinc-800 p-3"
            >
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="min-w-0">
                  <div className="font-medium">
                    <ProdutoLabel nome={p.produto_nome} id={p.produto_id} />
                  </div>
                  <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                    Quantidade {p.quantidade}
                    {p.valor_reserva != null && <> · preço mínimo R$ {p.valor_reserva}</>}
                    {' · '}
                    {(p.empresas_compradoras?.length ?? 0)} comprador(es) na disputa
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={busy === p.processo_id}
                    onClick={() => decidir(p.processo_id, 'sim')}
                  >
                    {busy === p.processo_id ? '…' : 'Abrir leilão'}
                  </button>
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={busy === p.processo_id}
                    onClick={() => decidir(p.processo_id, 'nao')}
                  >
                    Recusar
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {log.length > 0 && (
        <div className="mt-5 pt-4 border-t border-zinc-200 dark:border-zinc-800">
          <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">
            Suas decisões recentes
          </h3>
          <ul className="space-y-1.5">
            {log.slice(0, 6).map((d, i) => (
              <li
                key={`${d.processo_id}-${i}`}
                className="flex items-center justify-between text-sm"
              >
                <span className="truncate">
                  <ProdutoLabel nome={d.produto_nome} id={d.produto_id} />
                </span>
                <span className="flex items-center gap-2 shrink-0">
                  <span className={d.decisao === 'sim' ? 'chip-ok' : 'chip-warn'}>
                    {d.decisao === 'sim' ? 'abriu' : 'recusou'}
                  </span>
                  <span className="text-xs text-zinc-400">{fmtDate(d.data)}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
