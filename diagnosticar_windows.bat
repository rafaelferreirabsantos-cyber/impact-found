@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py diagnosticar_rede.py
) else (
  python diagnosticar_rede.py
)
echo.
echo Se algum teste falhou, veja diagnostico_rede.txt nesta pasta.
pause
