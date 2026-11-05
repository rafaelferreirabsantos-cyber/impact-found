@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -m pip install -r requirements.txt
  if errorlevel 1 goto erro
  py -m src.market_server --provider brapi --refresh-min 30
) else (
  python -m pip install -r requirements.txt
  if errorlevel 1 goto erro
  python -m src.market_server --provider brapi --refresh-min 30
)
goto fim
:erro
echo Nao foi possivel iniciar o monitor. Verifique conexao e Python.
:fim
pause
