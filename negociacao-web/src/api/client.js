import axios from 'axios';
import { getJwt, clearJwt } from '../lib/jwt-handshake.js';

function resolveBase() {
  if (import.meta.env.VITE_API_BASE) return import.meta.env.VITE_API_BASE;
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') {
    return `${window.location.protocol}//${window.location.host}/api/negociacoes`;
  }
  return 'http://localhost:5006';
}
const BASE = resolveBase();

export const api = axios.create({ baseURL: BASE });

api.interceptors.request.use((cfg) => {
  const token = getJwt();
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      clearJwt();
    }
    return Promise.reject(err);
  }
);

// URL do stream SSE (EventSource não envia header Authorization → token na query).
export function streamLancesUrl(processoId) {
  const token = getJwt() || '';
  return `${BASE}/processos/${processoId}/stream?jwt=${encodeURIComponent(token)}`;
}

export const NegociacaoApi = {
  listarProcessos: (params = {}) =>
    api.get('/processos', { params }).then((r) => r.data),
  abertosParaMim: () =>
    api.get('/processos/abertos-para-mim').then((r) => r.data),
  detalhe: (id) =>
    api.get(`/processos/${id}`).then((r) => r.data),
  registrarLance: (id, body) =>
    api.post(`/processos/${id}/lances`, body).then((r) => r.data),
  fechar: (id) =>
    api.post(`/processos/${id}/fechar`).then((r) => r.data),
  listarProdutos: () => api.get('/produtos').then((r) => r.data),
};
