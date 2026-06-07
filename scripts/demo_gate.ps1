# Demo do gate de confirmacao do fornecedor (leilao direto) no stack local.
#
# Faz tudo de uma vez: cria uma proposta pendente -> fornecedor ABRE (gate = sim)
# -> 2 compradores dao lance -> imprime as URLs e abre o chat no navegador.
# O leilao fica aberto ~5 min (MERCADO_DEFAULT_AUCTION_DURATION_SECONDS no .env.local).
#
# Uso (na raiz do projeto):
#   .\scripts\demo_gate.ps1              # cria, abre, da 2 lances e abre o chat
#   .\scripts\demo_gate.ps1 -NoBids      # so cria e abre (sem lances) p/ bidar ao vivo
#   .\scripts\demo_gate.ps1 -NoBrowser   # nao abre o navegador, so imprime as URLs
#
# Pre-requisito: stack local de pe (docker compose -f docker-compose.yml -f docker-compose.local.yml up -d).

param(
    [switch]$NoBids,
    [switch]$NoBrowser
)

# Obs: NAO usar $ErrorActionPreference = "Stop" aqui — o seed escreve progresso
# em stderr e o PowerShell 5.1 trataria isso como erro fatal. O Invoke-RestMethod
# ja lanca sozinho em erro HTTP, que e o que importa.
$MERCADO = "http://localhost:5005"
$NEGOCIACAO = "http://localhost:5006"

function Mint([string]$EmpresaId, [string]$Role) {
    return (docker exec negociacao-service python /tmp/mint_jwt.py $EmpresaId $Role).Trim()
}
function Get-EmpresaId([string]$Cnpj) {
    return (docker exec -e PGPASSWORD=postgres_admin_local vendas-postgres psql -U postgres -d portal_b2b -t -A -c "SELECT id FROM portal_b2b.empresa WHERE cnpj='$Cnpj'").Trim()
}

Write-Host "==> Copiando scripts para o container..." -ForegroundColor Cyan
docker cp scripts\mint_jwt.py negociacao-service:/tmp/mint_jwt.py | Out-Null
docker cp scripts\seed_proposta_pendente.py negociacao-service:/tmp/seed.py | Out-Null

Write-Host "==> Criando proposta pendente (leilao direto)..." -ForegroundColor Cyan
docker exec negociacao-service python /tmp/seed.py 2>$null | Out-Null
Start-Sleep -Seconds 3

# As empresas tem cnpj fixo no seed; pegamos os ids do banco (robusto a reset de volume).
$forn  = Get-EmpresaId "00000000000001"
$compA = Get-EmpresaId "00000000000003"
$compB = Get-EmpresaId "00000000000004"
$ftok  = Mint $forn  "FORNECEDOR"
$cAtok = Mint $compA "COMPRADOR"
$cBtok = Mint $compB "COMPRADOR"

$props = Invoke-RestMethod -Uri "$MERCADO/propostas?fornecedor_id=$forn" -Headers @{ Authorization = "Bearer $ftok" }
$prop = @($props) | Sort-Object criada_em | Select-Object -Last 1
if (-not $prop) {
    Write-Host "ERRO: nenhuma proposta pendente apareceu. O mercado-service consumiu os eventos?" -ForegroundColor Red
    exit 1
}
$procId = $prop.processo_id
Write-Host "    proposta $procId  ($($prop.produto_nome))" -ForegroundColor DarkGray

Write-Host "==> Fornecedor ABRE o leilao (gate = sim)..." -ForegroundColor Cyan
$open = Invoke-RestMethod -Method Post -Uri "$MERCADO/propostas/$procId/confirmar" -Headers @{ Authorization = "Bearer $ftok" } -ContentType "application/json" -Body '{"decisao":"sim"}'
Write-Host "    status: $($open.status)" -ForegroundColor DarkGray
Start-Sleep -Seconds 4   # negociacao consome o evento e cria o processo

if (-not $NoBids) {
    Write-Host "==> Compradores dao lance..." -ForegroundColor Cyan
    $l1 = Invoke-RestMethod -Method Post -Uri "$NEGOCIACAO/processos/$procId/lances" -Headers @{ Authorization = "Bearer $cAtok" } -ContentType "application/json" -Body '{"valor_unitario":"11.50","quantidade":"50"}'
    Write-Host "    Comprador A: R$ $($l1.valor_unitario)" -ForegroundColor DarkGray
    $l2 = Invoke-RestMethod -Method Post -Uri "$NEGOCIACAO/processos/$procId/lances" -Headers @{ Authorization = "Bearer $cBtok" } -ContentType "application/json" -Body '{"valor_unitario":"12.00","quantidade":"50"}'
    Write-Host "    Comprador B: R$ $($l2.valor_unitario)" -ForegroundColor DarkGray
}

$urlForn = "http://localhost:8085/?jwt=$ftok"
$urlA = "http://localhost:8086/?jwt=$cAtok"
$urlB = "http://localhost:8086/?jwt=$cBtok"

Write-Host ""
Write-Host "Leilao ABERTO (~5 min). URLs prontas:" -ForegroundColor Green
Write-Host "  Fornecedor  (mercado-web): $urlForn"
Write-Host "  Comprador A (chat):        $urlA"
Write-Host "  Comprador B (chat):        $urlB"

if (-not $NoBrowser) {
    Start-Process $urlA
}
