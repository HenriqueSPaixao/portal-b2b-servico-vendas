import axios from 'axios';
import { getJwt, clearJwt } from '../lib/jwt-handshake.js';

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5005';

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
  listarProcessos: () => api.get('/api/mercado/processos').then((r) => r.data),
  snapshot: (produtoId) =>
    api.get(`/api/mercado/snapshot/${produtoId}`).then((r) => r.data),
};
