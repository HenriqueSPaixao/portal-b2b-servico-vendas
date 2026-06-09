import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { NegociacaoApi, streamLancesUrl } from '../api/client.js';
import { getJwt, currentRole, currentEmpresaId } from '../lib/jwt-handshake.js';
import { MODO_COLORS, STATUS_COLORS, truncate, fmtDate, fmtBRL, fmtQty } from '../lib/format.js';
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

  // Tempo real via SSE: quando um lance entra, recarrega na hora. O polling de 5s
  // acima fica como rede de segurança (se o SSE cair ou houver multi-instância).
  useEffect(() => {
    if (!getJwt()) return undefined;
    let es;
    try {
      es = new EventSource(streamLancesUrl(id));
      es.addEventListener('lance', () => load());
      // onerror: o EventSource já tenta reconectar sozinho; o polling cobre o gap.
    } catch {
      // EventSource indisponível neste ambiente — polling cobre.
    }
    return () => es?.close();
  }, [id, load]);

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

  // Quem dá lance depende do modo: no leilão direto competem os COMPRADORES;
  // no reverso, os FORNECEDORES. Mostramos o formulário só pra esse lado; o outro
  // lado "acompanha". (O backend ainda valida a habilitação — isto é só UX.)
  const role = currentRole();
  const bidderRole =
    processo?.modo === 'leilao_direto'
      ? 'COMPRADOR'
      : processo?.modo === 'leilao_reverso'
        ? 'FORNECEDOR'
        : null;
  // Sem papel no token, deixamos o backend decidir (mostra o form).
  const podeBidar = bidderRole ? !role || role === bidderRole : false;
  const ladoQueBida = bidderRole === 'COMPRADOR' ? 'compradores' : 'fornecedores';

  // Valor a bater: melhor lance até agora (maior no direto, menor no reverso);
  // se ninguém deu lance, cai no preço de referência do leilão.
  const isReverso = processo?.modo === 'leilao_reverso';
  const lances = processo?.lances || [];
  const valores = lances
    .map((l) => Number(l.valor_unitario))
    .filter((n) => !Number.isNaN(n));
  const melhorLance = valores.length
    ? (isReverso ? Math.min(...valores) : Math.max(...valores))
    : null;
  const valorReferencia = processo?.valor_reserva != null ? Number(processo.valor_reserva) : null;
  const valorAlvo = melhorLance != null ? melhorLance : valorReferencia;
  const papelLabel =
    role === 'FORNECEDOR' ? 'Fornecedor' : role === 'COMPRADOR' ? 'Comprador' : null;

  // Estado de encerramento: o lance vencedor é o melhor da lista (maior no direto,
  // menor no reverso) — mesma regra do backend em _calcular_vencedor. Como cada lance
  // precisa SUPERAR o anterior, não há empate, então o cálculo aqui é determinístico.
  const isLeilao = processo?.modo === 'leilao_direto' || processo?.modo === 'leilao_reverso';
  const encerrado = processo != null && processo.status !== 'ABERTO';
  const vencedor =
    isLeilao && lances.length
      ? lances.reduce((best, l) => {
          const v = Number(l.valor_unitario);
          const bv = Number(best.valor_unitario);
          if (Number.isNaN(v)) return best;
          return isReverso ? (v < bv ? l : best) : (v > bv ? l : best);
        }, lances[0])
      : null;
  const me = currentEmpresaId();
  const vencedorMine = vencedor && me && vencedor.empresa_id === me;

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
              <InfoRow label="Preço de referência">{fmtBRL(processo.valor_reserva)}</InfoRow>
            </div>
          </div>

          {encerrado && isLeilao && vencedor && (
            <div className="card border border-brand-green/40 bg-brand-green/5">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold">🏆 Leilão encerrado — lance vencedor</h2>
                <span className="chip bg-brand-green/15 text-brand-green">
                  {isReverso ? 'menor preço' : 'maior preço'}
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <InfoRow label={isReverso ? 'Fornecedor vencedor' : 'Comprador vencedor'}>
                  {vencedorMine ? (
                    <strong className="text-brand-green">Você</strong>
                  ) : (
                    <span className="font-mono text-xs" title={vencedor.empresa_id}>
                      {truncate(vencedor.empresa_id)}
                    </span>
                  )}
                </InfoRow>
                <InfoRow label="Preço por unidade">
                  <strong>{fmtBRL(vencedor.valor_unitario)}</strong>
                </InfoRow>
                <InfoRow label="Quantidade">{fmtQty(vencedor.quantidade)}</InfoRow>
                <InfoRow label="Valor total">
                  {fmtBRL(Number(vencedor.valor_unitario) * Number(vencedor.quantidade))}
                </InfoRow>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2">
                Venceu o {isReverso ? 'menor' : 'maior'} lance entre {lances.length} oferta(s).
                Ele está destacado na conversa abaixo.
              </p>
            </div>
          )}

          {encerrado && isLeilao && !vencedor && (
            <div className="card border border-amber-500/40 bg-amber-500/5">
              <h2 className="font-semibold mb-1">Leilão encerrado sem propostas</h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-300">
                O prazo terminou e <strong>ninguém deu lance</strong> neste leilão — ele fechou
                <strong> sem vencedor</strong> e nada foi negociado. É um desfecho válido: um
                leilão pode encerrar vazio.
              </p>
            </div>
          )}

          {encerrado && processo.modo === 'direto' && (
            <div className="card">
              <h2 className="font-semibold mb-1">Venda direta concluída</h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-300">
                Modo de venda direta: fechou automaticamente ao preço de referência, sem disputa
                de lances.
              </p>
            </div>
          )}

          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold">Negociação — fornecedor e comprador</h2>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                {processo.lances?.length || 0} lance(s)
                {encerrado ? ' · encerrado' : ' · ao vivo (tempo real)'}
              </span>
            </div>
            <LancesChat
              lances={processo.lances || []}
              vencedorId={encerrado ? vencedor?.id : null}
            />
          </div>

          {processo.status === 'ABERTO' && bidderRole && (
            <div className="card">
              <div className="flex items-center justify-between mb-2">
                <h2 className="font-semibold">Situação do leilão</h2>
                {papelLabel && (
                  <span className="chip bg-brand-green/10 text-brand-green">
                    Você está como {papelLabel}
                  </span>
                )}
              </div>
              {valorAlvo != null ? (
                <>
                  <div className="text-xs text-zinc-500 dark:text-zinc-400">
                    {melhorLance != null ? 'Melhor lance até agora' : 'Preço de referência'}
                  </div>
                  <div className="text-3xl font-bold tracking-tight">{fmtBRL(valorAlvo)}</div>
                  {podeBidar && (
                    <p className="text-sm mt-1 text-zinc-600 dark:text-zinc-300">
                      {melhorLance != null ? (
                        isReverso ? (
                          <>Para assumir a liderança, ofereça <strong>menos</strong> que {fmtBRL(valorAlvo)}.</>
                        ) : (
                          <>Para assumir a liderança, dê um lance <strong>maior</strong> que {fmtBRL(valorAlvo)}.</>
                        )
                      ) : isReverso ? (
                        <>Ninguém ofereceu ainda — o valor <strong>máximo</strong> aceito é {fmtBRL(valorAlvo)}.</>
                      ) : (
                        <>Ninguém deu lance ainda — o lance <strong>mínimo</strong> é {fmtBRL(valorAlvo)}.</>
                      )}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-zinc-600 dark:text-zinc-300">
                  Ninguém deu lance ainda. Faça a primeira oferta!
                </p>
              )}
              {melhorLance == null && (
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">
                  Se ninguém der lance até o encerramento, o leilão fecha <strong>sem
                  proposta</strong> (sem vencedor).
                </p>
              )}
              {processo.quantidade != null && (
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2">
                  Lote de <strong>{fmtQty(processo.quantidade)} unidades</strong> — o lance é
                  pelo lote inteiro; a disputa é só no preço por unidade.
                </p>
              )}
            </div>
          )}

          {processo.status === 'ABERTO' && bidderRole && (
            <div className="card">
              {podeBidar ? (
                <>
                  <h2 className="font-semibold mb-3">Dar lance</h2>
                  <LanceForm
                    processoId={processo.id}
                    quantidade={processo.quantidade}
                    onSuccess={load}
                  />
                </>
              ) : (
                <>
                  <h2 className="font-semibold mb-1">Você está acompanhando</h2>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    Neste leilão, quem dá lances são os <strong>{ladoQueBida}</strong>.
                    Você acompanha a negociação em tempo real aqui.
                  </p>
                </>
              )}
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
