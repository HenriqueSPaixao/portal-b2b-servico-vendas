@echo off
REM Wrapper do smoke test do dominio Vendas - PowerShell / CMD nativos do Windows.
REM Uso: scripts\run_smoke.bat
REM
REM Pre-requisitos: docker compose -f docker-compose.yml -f docker-compose.local.yml up -d rodando.
REM Le JWT_SECRET do .env na raiz (gitignored). Sai com o exit code do smoke test.

setlocal enabledelayedexpansion

REM 1. Mover para a raiz do projeto.
cd /d "%~dp0\.."

REM 2. Verificar que negociacao-service esta rodando.
docker ps --format "{{.Names}}" | findstr /B /C:"negociacao-service" >nul
if errorlevel 1 (
    echo ERRO: container negociacao-service nao esta rodando.
    echo       Suba a stack antes: docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
    exit /b 1
)

REM 3. Pegar JWT_SECRET - preferencia: env var ja definida; fallback: .env.
if defined JWT_SECRET goto :have_secret
if not exist .env (
    echo ERRO: JWT_SECRET nao definido e .env nao existe.
    echo       Crie .env ^(copy .env.local .env^) ou defina a variavel JWT_SECRET.
    exit /b 1
)
for /f "tokens=1,* delims==" %%a in ('findstr /B "JWT_SECRET=" .env') do (
    set "JWT_SECRET=%%b"
)
if not defined JWT_SECRET (
    echo ERRO: JWT_SECRET ausente do .env.
    exit /b 1
)
:have_secret

REM 4. Copiar e executar.
echo Copiando smoke_test.py para o container...
docker cp scripts\smoke_test.py negociacao-service:/tmp/smoke.py
if errorlevel 1 exit /b 1

echo Executando smoke test...
docker exec -e JWT_SECRET=%JWT_SECRET% negociacao-service python /tmp/smoke.py
exit /b %errorlevel%
