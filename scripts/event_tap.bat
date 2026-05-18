@echo off
REM Wrapper do event_tap.py para Windows.
REM Copia o script para o container negociacao-service e roda - assim aproveita
REM o ambiente com aiokafka ja instalado.
REM
REM Uso:
REM     scripts\event_tap.bat                        REM todos os topicos
REM     scripts\event_tap.bat negociacao_fechada     REM filtra um
REM
REM Pre-requisito: docker compose up -d.

setlocal enabledelayedexpansion

cd /d "%~dp0\.."

docker ps --format "{{.Names}}" | findstr /B /C:"negociacao-service" >nul
if errorlevel 1 (
    echo ERRO: container negociacao-service nao esta rodando.
    echo       Suba a stack antes: docker compose up -d
    exit /b 1
)

docker cp scripts\event_tap.py negociacao-service:/tmp/event_tap.py
if errorlevel 1 exit /b 1

docker exec -i -e SMOKE_KAFKA=redpanda:9092 negociacao-service python /tmp/event_tap.py %*
exit /b %errorlevel%
