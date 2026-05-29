import axios from 'axios';
import { getJwt, clearJwt } from '../lib/jwt-handshake.js';

function resolveBase() {
  if (import.meta.env.VITE_API_BASE) return import.meta.env.VITE_API_BASE;
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') {
    return `${window.location.protocol}//${window.location.host}/api/mercado`;
  }
  return 'http://localhost:5005';
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

export const MercadoApi = {
  listarProcessos: () => api.get('/processos').then((r) => r.data),
  snapshot: (produtoId) =>
    api.get(`/snapshot/${produtoId}`).then((r) => r.data),
  listarProdutos: () => api.get('/produtos').then((r) => r.data),
};
