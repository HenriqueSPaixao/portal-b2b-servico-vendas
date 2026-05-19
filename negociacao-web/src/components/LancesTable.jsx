import { truncate, fmtDate } from '../lib/format.js';

export default function LancesTable({ lances }) {
  if (!lances || lances.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Nenhum lance registrado ainda.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto -mx-5">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
          <tr>
            <th className="px-5 py-2">Empresa</th>
            <th className="px-5 py-2 text-right">Valor unitário</th>
            <th className="px-5 py-2 text-right">Quantidade</th>
            <th className="px-5 py-2">Data</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {lances.map((l) => (
            <tr key={l.id}>
              <td className="px-5 py-2 font-mono text-xs" title={l.empresa_id}>{truncate(l.empresa_id)}</td>
              <td className="px-5 py-2 text-right font-mono">{l.valor_unitario}</td>
              <td className="px-5 py-2 text-right font-mono">{l.quantidade}</td>
              <td className="px-5 py-2">{fmtDate(l.data_lance)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
