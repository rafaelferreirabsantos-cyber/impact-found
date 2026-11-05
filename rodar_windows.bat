@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -m pip install -r requirements.txt
  if errorlevel 1 goto error
  py -m src.run
) else (
  python -m pip install -r requirements.txt
  if errorlevel 1 goto error
  python -m src.run
)
if errorlevel 1 goto error
echo.
echo Backtest gerado! Abra output\dashboard_com_resultados.html
pause
exit /b 0
:error
echo.
echo Nao foi possivel concluir. Copie a mensagem de erro acima para diagnostico.
pause
exit /b 1
