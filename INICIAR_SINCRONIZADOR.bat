@echo off
setlocal
cd /d "%~dp0"
title Sincronizador Operacional - Leo Madeiras
if not exist "sync_config.json" (
  echo ERRO: execute primeiro CONFIGURAR_SINCRONIZADOR.bat.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo ERRO: ambiente Python nao preparado. Execute CONFIGURAR_SINCRONIZADOR.bat.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" sync_agent.py
if errorlevel 1 pause
