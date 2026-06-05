import { fmtDate, truncate } from '../lib/format.js';
import { currentEmpresaId } from '../lib/jwt-handshake.js';

/**
 * Negociação como "chatzinho": cada lance é uma mensagem na conversa entre
 * fornecedor e comprador. Os lances da empresa logada saem à direita (verde);
 * os do outro lado, à esquerda. A lista atualiza junto com o polling do detalhe.
 */
export default function LancesChat({ lances }) {
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
        return (
          <div key={l.id} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
            <div
              className={
                'max-w-[80%] rounded-2xl px-4 py-2 ' +
                (mine
                  ? 'bg-brand-green text-white rounded-br-sm'
                  : 'bg-zinc-100 text-zinc-900 rounded-bl-sm dark:bg-zinc-800 dark:text-zinc-100')
              }
            >
              <div
                className={
                  'text-[11px] mb-0.5 ' +
                  (mine ? 'text-white/80' : 'text-zinc-500 dark:text-zinc-400')
                }
                title={l.empresa_id}
              >
                {mine ? 'Você' : `Empresa ${truncate(l.empresa_id)}`}
              </div>
              <div className="font-semibold leading-tight">
                R$ {l.valor_unitario}
                <span className="font-normal text-sm opacity-80"> × {l.quantidade}</span>
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
