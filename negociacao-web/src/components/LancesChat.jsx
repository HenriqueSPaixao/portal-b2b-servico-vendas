import { fmtDate, truncate, fmtBRL, fmtQty } from '../lib/format.js';
import { currentEmpresaId } from '../lib/jwt-handshake.js';

/**
 * Negociação como "chatzinho": cada lance é uma mensagem na conversa entre
 * fornecedor e comprador. Os lances da empresa logada saem à direita (verde);
 * os do outro lado, à esquerda. A lista atualiza junto com o polling do detalhe.
 */
export default function LancesChat({ lances, vencedorId = null }) {
  const me = currentEmpresaId();

  if (!lances || lances.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Ainda sem propostas. Os lances de fornecedor e comprador aparecem aqui como
        uma conversa, do mais antigo ao mais recente.
      </p>
    );
  }

  const ordenados = [...lances].sort(
    (a, b) => new Date(a.data_lance) - new Date(b.data_lance)
  );

  return (
    <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
      {ordenados.map((l) => {
        const mine = me && l.empresa_id === me;
        const venceu = vencedorId && l.id === vencedorId;
        return (
          <div key={l.id} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
            <div
              className={
                'max-w-[80%] rounded-2xl px-4 py-2 ' +
                (venceu ? 'ring-2 ring-brand-green ring-offset-1 dark:ring-offset-zinc-900 ' : '') +
                (mine
                  ? 'bg-brand-green text-white rounded-br-sm'
                  : 'bg-zinc-100 text-zinc-900 rounded-bl-sm dark:bg-zinc-800 dark:text-zinc-100')
              }
            >
              <div
                className={
                  'text-[11px] mb-0.5 flex items-center gap-1 ' +
                  (mine ? 'text-white/80' : 'text-zinc-500 dark:text-zinc-400')
                }
                title={l.empresa_id}
              >
                <span>{mine ? 'Você' : `Empresa ${truncate(l.empresa_id)}`}</span>
                {venceu && (
                  <span
                    className={
                      'chip text-[10px] ' +
                      (mine ? 'bg-white/20 text-white' : 'bg-brand-green/15 text-brand-green')
                    }
                  >
                    🏆 Vencedor
                  </span>
                )}
              </div>
              <div className="font-semibold leading-tight">
                {fmtBRL(l.valor_unitario)}
                <span className="font-normal text-sm opacity-80"> × {fmtQty(l.quantidade)}</span>
              </div>
              <div
                className={
                  'text-[10px] mt-0.5 text-right ' +
                  (mine ? 'text-white/70' : 'text-zinc-400')
                }
              >
                {fmtDate(l.data_lance)}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
