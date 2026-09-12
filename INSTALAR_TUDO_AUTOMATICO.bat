@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title LEO Madeiras - Instalacao automatica completa

echo ============================================================
echo   ACOMPANHAMENTO OPERACIONAL - INSTALACAO AUTOMATICA
echo ============================================================
echo.
set "PYTHON_EXE="
set "VENV_PY=.venv\Scripts\python.exe"

echo [1/8] Verificando Windows e PowerShell...
where powershell.exe >nul 2>&1 || goto :sem_powershell

echo [2/8] Localizando uma instalacao valida do Python...
if exist "%VENV_PY%" (
  "%VENV_PY%" -c "import sys; assert sys.version_info >= (3,9)" >nul 2>&1
  if not errorlevel 1 set "PYTHON_EXE=%CD%\%VENV_PY%"
)
if defined PYTHON_EXE goto :venv_pronto
where py.exe >nul 2>&1
if not errorlevel 1 for /f "usebackq delims=" %%P in (`py -3 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE (
  where python.exe >nul 2>&1
  if not errorlevel 1 for /f "usebackq delims=" %%P in (`python -c "import sys; print(sys.executable)" 2^>nul`) do set "PYTHON_EXE=%%P"
)
if defined PYTHON_EXE (
  "%PYTHON_EXE%" -c "import sys; assert sys.version_info >= (3,9)" >nul 2>&1
  if errorlevel 1 set "PYTHON_EXE="
)
if not defined PYTHON_EXE call :instalar_python
if not defined PYTHON_EXE goto :sem_python

echo [3/8] Criando ou reparando o ambiente virtual...
if exist ".venv" move ".venv" ".venv_invalido_%RANDOM%" >nul 2>&1
if not exist "%VENV_PY%" "%PYTHON_EXE%" -m venv .venv || goto :erro_venv

:venv_pronto
set "PYTHON_EXE=%CD%\%VENV_PY%"
echo [4/8] Atualizando o instalador de pacotes...
"%PYTHON_EXE%" -m ensurepip --upgrade >nul 2>&1
"%PYTHON_EXE%" -m pip install --upgrade pip setuptools wheel || goto :erro_dependencias

echo [5/8] Instalando e conferindo todas as dependencias...
"%PYTHON_EXE%" -m pip install -r requirements.txt || goto :erro_dependencias
"%PYTHON_EXE%" -c "import fastapi,uvicorn,jinja2,multipart,polars,pyarrow,duckdb,apscheduler,openpyxl,httpx,reportlab; print('Dependencias validadas com sucesso.')" || goto :erro_validacao

echo [6/8] Verificando configuracao de acesso ao Railway...
if not exist "sync_config.json" "%PYTHON_EXE%" configurar_sync.py || goto :erro_config
echo As fontes serao obtidas automaticamente da tela Configuracoes.

echo [7/8] Testando conexao e primeiro envio...
"%PYTHON_EXE%" sync_agent.py --once || goto :erro_envio

echo [8/8] Ativando sincronizacao automatica no Windows...
call INSTALAR_SINCRONIZADOR_AUTOMATICO.bat || goto :erro_inicio
echo.
echo ============================================================
echo   INSTALACAO CONCLUIDA COM SUCESSO
echo ============================================================
echo O sincronizador verificara alteracoes automaticamente.
pause
exit /b 0

:instalar_python
echo Python compativel nao encontrado. Instalando Python 3.12...
where winget.exe >nul 2>&1
if not errorlevel 1 winget install --id Python.Python.3.12 --exact --scope user --silent --accept-package-agreements --accept-source-agreements
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
if defined PYTHON_EXE exit /b 0
echo Tentando instalacao oficial alternativa...
set "PYTHON_INSTALLER=%TEMP%\python-3.12.10-amd64.exe"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $env:PYTHON_INSTALLER" || exit /b 1
if not exist "%PYTHON_INSTALLER%" exit /b 1
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_tcltk=1 Include_test=0 Shortcuts=0
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
exit /b 0

:sem_powershell
echo ERRO: Windows PowerShell nao foi encontrado.
goto :falha
:sem_python
echo ERRO: Python nao localizado e instalacao automatica bloqueada.
goto :falha
:erro_venv
echo ERRO: nao foi possivel criar o ambiente virtual.
goto :falha
:erro_dependencias
echo ERRO: falha ao instalar as dependencias.
goto :falha
:erro_validacao
echo ERRO: uma dependencia nao passou na validacao.
goto :falha
:erro_config
echo ERRO: configuracao do Railway ou das fontes nao concluida.
goto :falha
:erro_envio
echo ERRO: a conexao ou o primeiro envio para o Railway falhou.
goto :falha
:erro_inicio
echo ERRO: nao foi possivel ativar a inicializacao automatica.
:falha
echo.
echo A instalacao nao foi concluida. Copie esta tela para diagnostico.
pause
exit /b 1
