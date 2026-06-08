# Abre uma UI local JA LOGADA — minta o JWT e abre o navegador na URL com ?jwt=,
# sem voce copiar/colar token nenhum.
#
# Uso (com a stack de pe):
#   .\scripts\abrir_local.ps1                         # negociacao-web, papel COMPRADOR
#   .\scripts\abrir_local.ps1 -Front mercado          # mercado-web, papel FORNECEDOR (gate)
#   .\scripts\abrir_local.ps1 -Role FORNECEDOR        # escolhe o papel
#   .\scripts\abrir_local.ps1 -EmpresaId <uuid>       # empresa especifica (default: aleatoria)
#   .\scripts\abrir_local.ps1 -NoBrowser              # so imprime a URL, nao abre o navegador
#
# Para um fluxo com dados (proposta + lances), use .\scripts\demo_gate.ps1.

param(
    [ValidateSet('mercado', 'negociacao')]
    [string]$Front = 'negociacao',
    [string]$Role,
    [string]$EmpresaId,
    [switch]$NoBrowser
)

# Default de papel coerente com cada front: no mercado-web quem age e o fornecedor
# (gate); na negociacao-web o caso comum e o comprador dando lance no leilao direto.
if (-not $Role) {
    $Role = if ($Front -eq 'mercado') { 'FORNECEDOR' } else { 'COMPRADOR' }
}
if (-not $EmpresaId) {
    $EmpresaId = [guid]::NewGuid().ToString()
}

$healthUrl = if ($Front -eq 'mercado') { 'http://localhost:5005/health' } else { 'http://localhost:5006/health' }
try { Invoke-RestMethod $healthUrl -TimeoutSec 5 | Out-Null }
catch {
    Write-Host "Stack nao esta de pe. Suba: docker compose -f docker-compose.yml -f docker-compose.local.yml up -d" -ForegroundColor Red
    exit 1
}

# mint_jwt.py roda DENTRO do container (ja tem python-jose e o JWT_SECRET certo).
docker cp "$PSScriptRoot\mint_jwt.py" negociacao-service:/tmp/mint_jwt.py | Out-Null
$tok = (docker exec negociacao-service python /tmp/mint_jwt.py $EmpresaId $Role).Trim()
if (-not $tok) {
    Write-Host "Falha ao mintar o token (o negociacao-service esta de pe?)." -ForegroundColor Red
    exit 1
}

$port = if ($Front -eq 'mercado') { 8085 } else { 8086 }
$url = "http://localhost:$port/?jwt=$tok"

Write-Host ""
Write-Host "$Front-web  ($Role / empresa $EmpresaId):" -ForegroundColor Green
Write-Host "  $url"

if (-not $NoBrowser) {
    Start-Process $url
    Write-Host "  -> abrindo no navegador..." -ForegroundColor DarkGray
}
