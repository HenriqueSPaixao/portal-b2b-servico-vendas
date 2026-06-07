const KEY = 'portal_b2b_jwt';

export function bootstrapJwt() {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get('jwt');
  if (fromUrl) {
    sessionStorage.setItem(KEY, fromUrl);
    params.delete('jwt');
    const search = params.toString();
    const url = window.location.pathname + (search ? `?${search}` : '') + window.location.hash;
    window.history.replaceState({}, '', url);
  }
  return sessionStorage.getItem(KEY);
}

export function getJwt() {
  return sessionStorage.getItem(KEY);
}

export function clearJwt() {
  sessionStorage.removeItem(KEY);
}

/**
 * Lê o claim `empresa_id` do JWT (decodificação client-side, sem validar
 * assinatura — só para alinhar os balões do chat de lances: os seus à direita,
 * os do outro lado à esquerda). A validação real acontece no backend.
 */
export function currentEmpresaId() {
  return readClaim('empresa_id');
}

/** Papel da empresa logada, lido do JWT (FORNECEDOR | COMPRADOR | …). */
export function currentRole() {
  return readClaim('role');
}

function readClaim(name) {
  const token = getJwt();
  if (!token) return null;
  try {
    const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(part))[name] || null;
  } catch {
    return null;
  }
}
