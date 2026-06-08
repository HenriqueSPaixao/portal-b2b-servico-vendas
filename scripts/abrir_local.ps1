# Abre uma UI local JA LOGADA — minta o JWT e abre o navegador na URL com ?jwt=,
# sem voce copiar/colar token nenhum.
#
# Uso (com a stack de pe):
#   .\scripts\abrir_local.ps1                         # negociacao-web, papel COMPRADOR (tela VAZIA)
#   .\scripts\abrir_local.ps1 -Front mercado          # mercado-web, papel FORNECEDOR (tela VAZIA)
#   .\scripts\abrir_local.ps1 -Role FORNECEDOR        # escolhe o papel (login limpo)
#   .\scripts\abrir_local.ps1 -EmpresaId <uuid>       # empresa especifica (login limpo)
#   .\scripts\abrir_local.ps1 -NoBrowser              # so imprime a URL, nao abre o navegador
#
#   -ComDados: alem de logar, SEMEIA um cenario pra voce ter o que testar na tela.
#     .\scripts\abrir_local.ps1 -Front mercado -ComDados   # cria proposta pendente e
#         loga como o FORNECEDOR dono -> painel 'Leiloes aguardando voce' (Abrir/Recusar).
#     .\scripts\abrir_local.ps1 -ComDados                  # cria proposta, fornecedor ABRE
#         (gate=sim) e loga como um COMPRADOR habilitado -> da pra dar lance no leilao.
#     Obs: com -ComDados, -Role/-EmpresaId sao ignorados (a empresa tem que casar com o
#     cenario semeado). Para a versao com 2 lances ja postados, use .\scripts\demo_gate.ps1.

param(
    [ValidateSet('mercado', 'negociacao')]
    [string]$Front = 'negociacao',
    [string]$Role,
    [string]$EmpresaId,
    [switch]$ComDados,
    [switch]$NoBrowser
)

$MERCADO = 'http://localhost:5005'
$NEG = 'http://localhost:5006'

function Test-Up([string]$Url) {
    try { Invoke-RestMethod $Url -TimeoutSec 5 | Out-Null; return $true } catch { return $false }
}
function Get-EmpresaId([string]$Cnpj) {
    (docker exec -e PGPASSWORD=postgres_admin_local vendas-postgres psql -U postgres -d portal_b2b -t -A -c "SELECT id FROM portal_b2b.empresa WHERE cnpj='$Cnpj'").Trim()
}
function Mint([string]$Id, [string]$Papel) {
    (docker exec negociacao-service python /tmp/mint_jwt.py $Id $Papel).Trim()
}

# -ComDados toca os dois services (semeia via negociacao, confere/abre via mercado);
# login limpo so precisa do service do front escolhido.
$need = if ($ComDados) { @($MERCADO, $NEG) } elseif ($Front -eq 'mercado') { @($MERCADO) } else { @($NEG) }
foreach ($u in $need) {
    if (-not (Test-Up "$u/health")) {
        Write-Host "Stack nao esta de pe. Suba: docker compose -f docker-compose.yml -f docker-compose.local.yml up -d" -ForegroundColor Red
        exit 1
    }
}

# mint_jwt.py roda DENTRO do container (ja tem python-jose e o JWT_SECRET certo).
docker cp "$PSScriptRoot\mint_jwt.py" negociacao-service:/tmp/mint_jwt.py | Out-Null

if ($ComDados) {
    docker cp "$PSScriptRoot\seed_proposta_pendente.py" negociacao-service:/tmp/seed.py | Out-Null
    Write-Host "==> Criando proposta pendente (leilao direto)..." -ForegroundColor Cyan
    docker exec negociacao-service python /tmp/seed.py 2>$null | Out-Null
    Start-Sleep -Seconds 3

    # As empresas tem cnpj fixo no seed; pegamos os ids do banco (robusto a reset de volume).
    $forn = Get-EmpresaId "00000000000001"
    $ftok = Mint $forn "FORNECEDOR"
    $props = Invoke-RestMethod -Uri "$MERCADO/propostas?fornecedor_id=$forn" -Headers @{ Authorization = "Bearer $ftok" }
    $prop = @($props) | Sort-Object criada_em | Select-Object -Last 1
    if (-not $prop) {
        Write-Host "ERRO: nenhuma proposta pendente apareceu (o mercado consumiu os eventos?)." -ForegroundColor Red
        exit 1
    }
    $procId = $prop.processo_id

    if ($Front -eq 'mercado') {
        # Painel do fornecedor: loga como o dono -> ve o leilao aguardando (Abrir/Recusar).
        $EmpresaId = $forn; $Role = 'FORNECEDOR'; $tok = $ftok
        Write-Host "    proposta $procId ($($prop.produto_nome)) aguardando o fornecedor" -ForegroundColor DarkGray
    }
    else {
        # Negociacao: o fornecedor ABRE o leilao e logamos como um COMPRADOR habilitado,
        # entao o leilao aparece em 'Leiloes abertos para voce' e da pra dar lance.
        Write-Host "==> Fornecedor ABRE o leilao (gate=sim)..." -ForegroundColor Cyan
        Invoke-RestMethod -Method Post -Uri "$MERCADO/propostas/$procId/confirmar" -Headers @{ Authorization = "Bearer $ftok" } -ContentType "application/json" -Body '{"decisao":"sim"}' | Out-Null
        Start-Sleep -Seconds 4   # negociacao consome o evento e cria o processo ABERTO
        $EmpresaId = Get-EmpresaId "00000000000003"; $Role = 'COMPRADOR'; $tok = Mint $EmpresaId 'COMPRADOR'
        Write-Host "    leilao $procId ABERTO -> logando como comprador habilitado" -ForegroundColor DarkGray
    }
}
else {
    # Login limpo (tela vazia): papel default coerente com o front, empresa aleatoria.
    if (-not $Role) {
        $Role = if ($Front -eq 'mercado') { 'FORNECEDOR' } else { 'COMPRADOR' }
    }
    if (-not $EmpresaId) {
        $EmpresaId = [guid]::NewGuid().ToString()
    }
    $tok = Mint $EmpresaId $Role
}

if (-not $tok) {
    Write-Host "Falha ao mintar o token (o negociacao-service esta de pe?)." -ForegroundColor Red
    exit 1
}

$port = if ($Front -eq 'mercado') { 8085 } else { 8086 }
$url = "http://localhost:$port/?jwt=$tok"

Write-Host ""
Write-Host "$Front-web  ($Role / empresa $EmpresaId):" -ForegroundColor Green
Write-Host "  $url"
if ($ComDados) {
    $dica = if ($Front -eq 'mercado') { "no painel 'Leiloes aguardando voce', clique Abrir leilao ou Recusar." }
            else { "abra o leilao em 'Leiloes abertos para voce' e de um lance." }
    Write-Host "  -> $dica" -ForegroundColor DarkGray
}

if (-not $NoBrowser) {
    Start-Process $url
    Write-Host "  -> abrindo no navegador..." -ForegroundColor DarkGray
}
