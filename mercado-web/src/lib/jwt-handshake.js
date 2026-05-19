const KEY = 'portal_b2b_jwt';

export function bootstrapJwt() {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get('jwt');
  if (fromUrl) {
    sessionStorage.setItem(KEY, fromUrl);
    params.delete('jwt');
    const search = params.toString();
    const url = window.location.pathname + (search ? `?${search}` : '');
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
