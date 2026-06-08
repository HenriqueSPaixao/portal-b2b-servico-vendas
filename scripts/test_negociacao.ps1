# Teste INTEGRAL do dominio de negociacao contra o stack LOCAL.
#
# Cobre, com resumo PASS/FAIL:
#   1) Fluxo event-driven A-E (smoke): 3 modos + gate do fornecedor + recusa.
#   2) Validacao de lance: piso/teto, supera o melhor, qtd <= disponivel, papel.
#   3) "Leiloes abertos para voce" (habilitacao por papel).
#   4) SSE (stream de lances ao vivo) com header X-Accel-Buffering.
#
# Uso (com o stack de pe):
#   .\scripts\test_negociacao.ps1
#
# Pre-requisito: docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

$MERCADO = "http://localhost:5005"
$NEG = "http://localhost:5006"
$pass = 0
$fail = 0

function Check($cond, $msg) {
    if ($cond) { Write-Host "  OK   $msg" -ForegroundColor Green; $script:pass++ }
    else { Write-Host "  FAIL $msg" -ForegroundColor Red; $script:fail++ }
}
function EId($cnpj) {
    (docker exec -e PGPASSWORD=postgres_admin_local vendas-postgres psql -U postgres -d portal_b2b -t -A -c "SELECT id FROM portal_b2b.empresa WHERE cnpj='$cnpj'").Trim()
}
function Mint($id, $role) {
    (docker exec negociacao-service python /tmp/mint_jwt.py $id $role).Trim()
}
function PostLance($tok, $v, $q) {
    try {
        Invoke-RestMethod -Method Post -Uri "$NEG/processos/$procId/lances" -Headers @{ Authorization = "Bearer $tok" } -ContentType "application/json" -Body (@{ valor_unitario = $v; quantidade = $q } | ConvertTo-Json) | Out-Null
        return 201
    } catch { return [int]$_.Exception.Response.StatusCode.value__ }
}

# Stack de pe?
try { Invoke-RestMethod "$NEG/health" -TimeoutSec 5 | Out-Null }
catch {
    Write-Host "Stack nao esta de pe. Suba: docker compose -f docker-compose.yml -f docker-compose.local.yml up -d" -ForegroundColor Red
    exit 1
}

# Tooling no container (o rebuild limpa /tmp).
docker cp "$PSScriptRoot\mint_jwt.py" negociacao-service:/tmp/mint_jwt.py | Out-Null
docker cp "$PSScriptRoot\seed_proposta_pendente.py" negociacao-service:/tmp/seed.py | Out-Null

# ----------------------------------------------------------------------------- #
Write-Host "`n=== 1/4  Smoke A-E (3 modos + gate + recusa) ===" -ForegroundColor Cyan
& "$PSScriptRoot\run_smoke.bat" 2>&1 | Select-Object -Last 7 | Write-Host
Check ($LASTEXITCODE -eq 0) "smoke A-E concluiu com exit 0"

# ----------------------------------------------------------------------------- #
Write-Host "`n=== 2/4  Validacao de lance (leilao direto: piso=10, qtd disponivel=50) ===" -ForegroundColor Cyan
$forn = EId "00000000000001"; $compA = EId "00000000000003"
$ftok = Mint $forn "FORNECEDOR"; $cAtok = Mint $compA "COMPRADOR"
docker exec negociacao-service python /tmp/seed.py 2>$null | Out-Null
Start-Sleep -Seconds 3
$props = Invoke-RestMethod -Uri "$MERCADO/propostas?fornecedor_id=$forn" -Headers @{ Authorization = "Bearer $ftok" }
$procId = (@($props) | Sort-Object criada_em | Select-Object -Last 1).processo_id
Invoke-RestMethod -Method Post -Uri "$MERCADO/propostas/$procId/confirmar" -Headers @{ Authorization = "Bearer $ftok" } -ContentType "application/json" -Body '{"decisao":"sim"}' | Out-Null
Start-Sleep -Seconds 4
Check ((PostLance $cAtok '5' '50') -eq 422)   "lance abaixo do piso (5<10) -> 422"
Check ((PostLance $cAtok '11' '50') -eq 201)  "lance valido (11) -> 201"
Check ((PostLance $cAtok '11' '50') -eq 422)  "lance que nao supera o melhor (11) -> 422"
Check ((PostLance $cAtok '12' '9999') -eq 422) "quantidade acima do disponivel -> 422"
Check ((PostLance $cAtok '12' '50') -eq 201)  "lance que sobe (12>11) -> 201"
Check ((PostLance $ftok '13' '50') -eq 403)   "fornecedor dando lance em leilao direto -> 403"

# ----------------------------------------------------------------------------- #
Write-Host "`n=== 3/4  Leiloes abertos para voce (habilitacao por papel) ===" -ForegroundColor Cyan
$alvo = "$procId"  # coage a string (evita quirk de comparacao de tipo do PowerShell)
$mineC = Invoke-RestMethod -Uri "$NEG/processos/abertos-para-mim" -Headers @{ Authorization = "Bearer $cAtok" }
$idsC = @($mineC | ForEach-Object { "$($_.id)" })
Check ($idsC -contains $alvo) "comprador A ve o leilao direto aberto"
$mineF = Invoke-RestMethod -Uri "$NEG/processos/abertos-para-mim" -Headers @{ Authorization = "Bearer $ftok" }
$idsF = @($mineF | ForEach-Object { "$($_.id)" })
Check (-not ($idsF -contains $alvo)) "fornecedor A NAO ve esse leilao direto"

# ----------------------------------------------------------------------------- #
Write-Host "`n=== 4/4  SSE (stream de lances ao vivo) ===" -ForegroundColor Cyan
$h = curl.exe -s -m 2 -D - -o NUL "$NEG/processos/$procId/stream?jwt=$cAtok" 2>$null
Check ($h -match "text/event-stream") "SSE content-type text/event-stream"
Check ($h -match "(?i)x-accel-buffering: no") "SSE envia X-Accel-Buffering: no (dispensa o gateway)"

# ----------------------------------------------------------------------------- #
Write-Host "`n=========== RESULTADO ===========" -ForegroundColor Cyan
Write-Host "  PASS: $pass    FAIL: $fail"
if ($fail -gt 0) {
    Write-Host "  ALGUM TESTE FALHOU" -ForegroundColor Red
    exit 1
}
Write-Host "  TUDO OK" -ForegroundColor Green
Write-Host "`nDica: para ver o SSE ao vivo na tela (2 navegadores), use .\scripts\demo_gate.ps1" -ForegroundColor DarkGray
exit 0
