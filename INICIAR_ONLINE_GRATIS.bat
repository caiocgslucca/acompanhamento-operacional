@echo off
setlocal EnableExtensions
title Acompanhamento Operacional - Acesso Online Gratis
cd /d "%~dp0"

echo ============================================================
echo   ACESSO ONLINE GRATIS - CLOUDFLARE TUNNEL
echo ============================================================
echo Nao exige cartao, conta ou liberacao de porta no Windows.
echo.

set "PYTHON_CMD="
where py >nul 2>&1 && set "PYTHON_CMD=py"
if not defined PYTHON_CMD where python >nul 2>&1 && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
  echo ERRO: Python nao localizado. Execute GERAR_EXE.bat uma vez para instalar.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente do projeto...
  "%PYTHON_CMD%" -m venv .venv
  if errorlevel 1 goto :falha
)

set "PY=.venv\Scripts\python.exe"
echo Verificando componentes...
"%PY%" -m pip install --disable-pip-version-check --prefer-binary -r requirements.txt
if errorlevel 1 goto :falha

"%PY%" online_launcher.py
exit /b %errorlevel%

:falha
echo.
echo ERRO: nao foi possivel preparar o acesso online.
pause
exit /b 1
