@echo off
setlocal
cd /d "%~dp0"
title Configurar Sincronizador Operacional
set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE where py >nul 2>&1 && set "PYTHON_EXE=py"
if not defined PYTHON_EXE where python >nul 2>&1 && set "PYTHON_EXE=python"
if not defined PYTHON_EXE (
  echo ERRO: Python nao encontrado.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  %PYTHON_EXE% -m venv .venv || goto :erro
  set "PYTHON_EXE=.venv\Scripts\python.exe"
)
"%PYTHON_EXE%" -m pip install -r requirements.txt || goto :erro
"%PYTHON_EXE%" configurar_sync.py || goto :erro
echo.
echo Executando o primeiro envio de teste...
"%PYTHON_EXE%" sync_agent.py --once || goto :erro
echo.
echo CONFIGURACAO CONCLUIDA COM SUCESSO.
call INSTALAR_SINCRONIZADOR_AUTOMATICO.bat
echo O sincronizador ficara ativo em segundo plano e iniciara com o Windows.
pause
exit /b 0
:erro
echo.
echo A configuracao nao foi concluida. Verifique a mensagem acima.
pause
exit /b 1
