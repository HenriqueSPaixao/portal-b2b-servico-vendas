import axios from 'axios';
import { getJwt, clearJwt } from '../lib/jwt-handshake.js';

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5006';

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

export const NegociacaoApi = {
  listarProcessos: (params = {}) =>
    api.get('/api/negociacao/processos', { params }).then((r) => r.data),
  detalhe: (id) =>
    api.get(`/api/negociacao/processos/${id}`).then((r) => r.data),
  registrarLance: (id, body) =>
    api.post(`/api/negociacao/processos/${id}/lances`, body).then((r) => r.data),
  fechar: (id) =>
    api.post(`/api/negociacao/processos/${id}/fechar`).then((r) => r.data),
};
