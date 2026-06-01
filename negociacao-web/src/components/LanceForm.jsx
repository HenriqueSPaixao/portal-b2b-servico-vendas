import { useState } from 'react';
import { NegociacaoApi } from '../api/client.js';

export default function LanceForm({ processoId, onSuccess }) {
  const [valor, setValor] = useState('');
  const [quantidade, setQuantidade] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    if (!valor || !quantidade) {
      setError('Preencha valor e quantidade.');
      return;
    }
    setSubmitting(true);
    try {
      await NegociacaoApi.registrarLance(processoId, {
        valor_unitario: valor,
        quantidade: quantidade,
      });
      setValor('');
      setQuantidade('');
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
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="lance-valor">Valor unitário</label>
          <input
            id="lance-valor"
            className="input"
            type="number"
            step="0.0001"
            min="0"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
            placeholder="12.50"
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="lance-qtd">Quantidade</label>
          <input
            id="lance-qtd"
            className="input"
            type="number"
            step="0.0001"
            min="0"
            value={quantidade}
            onChange={(e) => setQuantidade(e.target.value)}
            placeholder="100"
            required
          />
        </div>
      </div>
      {error && <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>}
      <button type="submit" className="btn-primary" disabled={submitting}>
        {submitting ? 'Enviando…' : 'Lançar'}
      </button>
    </form>
  );
}
