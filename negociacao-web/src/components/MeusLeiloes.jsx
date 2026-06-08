import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { NegociacaoApi } from '../api/client.js';
import { getJwt, currentRole } from '../lib/jwt-handshake.js';
import { fmtDate } from '../lib/format.js';

/**
 * Ponto de entrada do participante: leilões ABERTOS em que a empresa logada está
 * habilitada a dar lance (vem do GET /processos/abertos-para-mim). Responde "como
 * o leilão chega ao fornecedor": no reverso, todos os fornecedores do produto
 * aparecem aqui e competem. Some quando não há nada pra você.
 */
export default function MeusLeiloes() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const role = currentRole();

  useEffect(() => {
    let alive = true;
    async function load() {
      if (!getJwt()) return;
      try {
        const data = await NegociacaoApi.abertosParaMim();
        if (alive) setItems(Array.isArray(data) ? data : []);
      } catch {
        // silencioso: não atrapalha o resto da tela
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (items.length === 0) return null;

  const papel =
    role === 'FORNECEDOR' ? 'Fornecedor' : role === 'COMPRADOR' ? 'Comprador' : '';

  return (
    <div className="card mb-5 border-brand-green/40">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">
          Leilões abertos para você{papel && ` (${papel})`}
        </h2>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          você pode dar lance
        </span>
      </div>
      <ul className="space-y-2">
        {items.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              onClick={() => navigate(`/processos/${p.id}`)}
              className="w-full text-left rounded-md border border-zinc-200 dark:border-zinc-800 p-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 flex items-center justify-between gap-3"
            >
              <span className="min-w-0">
                <span className="font-medium">
                  {p.produto_nome || `${p.produto_id?.slice(0, 8)}…`}
                </span>
                <span className="block text-xs text-zinc-500 dark:text-zinc-400">
                  {p.modo === 'leilao_reverso'
                    ? 'Leilão reverso — você concorre baixando o preço'
                    : 'Leilão direto — você concorre subindo o preço'}
                  {' · fecha '}
                  {fmtDate(p.data_fim)}
                </span>
              </span>
              <span className="chip-ok shrink-0">Dar lance →</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
