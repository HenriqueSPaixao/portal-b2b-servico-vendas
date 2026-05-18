@echo off
REM Wrapper do event_publish.py para Windows.
REM
REM Uso:
REM     scripts\event_publish.bat ^<topico^> ^<fixture.json^>
REM Exemplo:
REM     scripts\event_publish.bat demanda_criada docs\integration\fixtures\demanda_criada.example.json

setlocal enabledelayedexpansion

cd /d "%~dp0\.."

docker ps --format "{{.Names}}" | findstr /B /C:"negociacao-service" >nul
if errorlevel 1 (
    echo ERRO: container negociacao-service nao esta rodando.
    echo       Suba a stack antes: docker compose up -d
    exit /b 1
)

if "%~1"=="" (
    echo Uso: %~nx0 ^<topico^> ^<fixture.json^>
    exit /b 2
)
if "%~2"=="" (
    echo Uso: %~nx0 ^<topico^> ^<fixture.json^>
    exit /b 2
)

set "TOPIC=%~1"
set "FIXTURE_HOST=%~2"
set "FIXTURE_BASENAME=%~nx2"

REM Copia o script e o fixture para o container.
docker cp scripts\event_publish.py negociacao-service:/tmp/event_publish.py
if errorlevel 1 exit /b 1
docker cp "%FIXTURE_HOST%" "negociacao-service:/tmp/%FIXTURE_BASENAME%"
if errorlevel 1 exit /b 1

shift
shift
docker exec -i -e SMOKE_KAFKA=redpanda:9092 negociacao-service ^
    python /tmp/event_publish.py %TOPIC% /tmp/%FIXTURE_BASENAME% %1 %2 %3
exit /b %errorlevel%
