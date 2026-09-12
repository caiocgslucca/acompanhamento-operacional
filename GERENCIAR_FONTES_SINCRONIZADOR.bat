@echo off
setlocal
cd /d "%~dp0"
title LEO Madeiras - Fontes do sincronizador

if not exist ".venv\Scripts\python.exe" (
    echo ERRO: ambiente Python nao encontrado.
    echo Execute primeiro CONFIGURAR_SINCRONIZADOR.bat.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" gerenciar_fontes_sync.py --interactive
if errorlevel 1 pause
