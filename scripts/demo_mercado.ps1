# Demo do MERCADO (gate do fornecedor): cria uma proposta de leilao direto
# PENDENTE e abre o mercado-web logado como o fornecedor, para VOCE clicar
# "Abrir leilao" ou "Recusar" na tela (a decisao fica com voce, nao confirma sozinho).
#
# Uso (com o stack de pe):
#   .\scripts\demo_mercado.ps1
#   .\scripts\demo_mercado.ps1 -NoBrowser   # so cria e imprime a URL
#
# Para alimentar a NEGOCIACAO (chat de lances) use .\scripts\demo_gate.ps1.

param(
    [switch]$NoBrowser
)

$MERCADO = "http://localhost:5005"

try { Invoke-RestMethod "$MERCADO/health" -TimeoutSec 5 | Out-Null }
catch {
    Write-Host "Stack nao esta de pe. Suba: docker compose -f docker-compose.yml -f docker-compose.local.yml up -d" -ForegroundColor Red
    exit 1
}

docker cp "$PSScriptRoot\mint_jwt.py" negociacao-service:/tmp/mint_jwt.py | Out-Null
docker cp "$PSScriptRoot\seed_proposta_pendente.py" negociacao-service:/tmp/seed.py | Out-Null

Write-Host "==> Criando proposta pendente (leilao direto, aguardando o fornecedor)..." -ForegroundColor Cyan
docker exec negociacao-service python /tmp/seed.py 2>$null | Out-Null
Start-Sleep -Seconds 3

$forn = (docker exec -e PGPASSWORD=postgres_admin_local vendas-postgres psql -U postgres -d portal_b2b -t -A -c "SELECT id FROM portal_b2b.empresa WHERE cnpj='00000000000001'").Trim()
$ftok = (docker exec negociacao-service python /tmp/mint_jwt.py $forn FORNECEDOR).Trim()

# Confere que a proposta apareceu para o fornecedor.
$props = Invoke-RestMethod -Uri "$MERCADO/propostas?fornecedor_id=$forn" -Headers @{ Authorization = "Bearer $ftok" }
Write-Host "    propostas pendentes para o fornecedor: $(@($props).Count)" -ForegroundColor DarkGray

$url = "http://localhost:8085/?jwt=$ftok"
Write-Host ""
Write-Host "Mercado-web (painel do fornecedor):" -ForegroundColor Green
Write-Host "  $url"
Write-Host "  -> no painel 'Leiloes aguardando voce', clique Abrir leilao ou Recusar." -ForegroundColor DarkGray

if (-not $NoBrowser) {
    Start-Process $url
}
