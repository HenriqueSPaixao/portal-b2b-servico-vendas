// Resolve o termo digitado na busca de produto para um produto_id.
// Prioridade: (1) nome exato — chave PRIMÁRIA; (2) id exato — chave SECUNDÁRIA;
// (3) um UUID avulso (mesmo que ainda não tenha `produto_cadastrado` no cache).
// Retorna null quando não dá pra resolver (o chamador decide a mensagem).

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function resolveProdutoId(termo, produtos = []) {
  const alvo = (termo || '').trim();
  if (!alvo) return null;
  const lower = alvo.toLowerCase();

  const porNome = produtos.find((p) => (p.nome || '').toLowerCase() === lower);
  if (porNome) return porNome.produto_id;

  const porId = produtos.find((p) => String(p.produto_id || '').toLowerCase() === lower);
  if (porId) return porId.produto_id;

  if (UUID_RE.test(alvo)) return alvo;
  return null;
}
