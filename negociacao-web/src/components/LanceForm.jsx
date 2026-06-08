import { useState } from 'react';
import { NegociacaoApi } from '../api/client.js';
import { fmtQty } from '../lib/format.js';

export default function LanceForm({ processoId, quantidade, onSuccess }) {
  const [valor, setValor] = useState('');
  const [qtdManual, setQtdManual] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Leilão de lote fechado: o lance é sempre pela quantidade do lote, e o
  // participante informa só o preço por unidade. Se a quantidade não vier
  // (processo sem metadata), caímos no campo manual como segurança.
  const loteFixo = quantidade != null && Number(quantidade) > 0;

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    const qtd = loteFixo ? String(quantidade) : qtdManual;
    if (!valor || !qtd) {
      setError(loteFixo ? 'Informe o preço por unidade.' : 'Preencha preço e quantidade.');
      return;
    }
    setSubmitting(true);
    try {
      await NegociacaoApi.registrarLance(processoId, {
        valor_unitario: valor,
        quantidade: qtd,
      });
      setValor('');
      setQtdManual('');
      onSuccess?.();
    } catch (err) {
      const msg = err.response?.data?.detail;
      setError(
        typeof msg === 'string' && msg
          ? msg
          : 'Não foi possível registrar o lance no momento. Tente novamente em alguns segundos.'
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {loteFixo && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Seu lance vale pelo lote inteiro de <strong>{fmtQty(quantidade)} unidades</strong>.
          Informe só o preço por unidade — quem oferecer o melhor preço leva o lote.
        </p>
      )}
      <div className={`grid grid-cols-1 gap-3 ${loteFixo ? '' : 'md:grid-cols-2'}`}>
        <div>
          <label className="label" htmlFor="lance-valor">Preço por unidade (R$)</label>
          <input
            id="lance-valor"
            className="input"
            type="number"
            step="0.01"
            min="0"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
            placeholder="12,50"
            required
          />
        </div>
        {!loteFixo && (
          <div>
            <label className="label" htmlFor="lance-qtd">Quantidade</label>
            <input
              id="lance-qtd"
              className="input"
              type="number"
              step="0.0001"
              min="0"
              value={qtdManual}
              onChange={(e) => setQtdManual(e.target.value)}
              placeholder="100"
            />
          </div>
        )}
      </div>
      {error && <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>}
      <button type="submit" className="btn-primary" disabled={submitting}>
        {submitting ? 'Enviando…' : 'Dar lance'}
      </button>
    </form>
  );
}
