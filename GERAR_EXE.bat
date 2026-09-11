@echo off
setlocal EnableExtensions
title Gerador - Acompanhamento Operacional
cd /d "%~dp0"

echo ============================================================
echo   ACOMPANHAMENTO OPERACIONAL - GERADOR DO EXECUTAVEL
echo ============================================================
echo.

set "PYTHON_CMD="
where py >nul 2>&1 && set "PYTHON_CMD=py"
if not defined PYTHON_CMD (
  where python >nul 2>&1 && set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD goto :instalar_python

if not exist ".venv\Scripts\python.exe" (
  echo [1/5] Criando ambiente isolado...
  "%PYTHON_CMD%" -m venv .venv
  if errorlevel 1 goto :falha
) else (
  echo [1/5] Ambiente isolado localizado.
)

set "PY=.venv\Scripts\python.exe"
:dependencias
echo [2/5] Verificando e instalando somente componentes ausentes...
"%PY%" -m ensurepip --upgrade >nul 2>&1
"%PY%" -m pip install --disable-pip-version-check --prefer-binary -r requirements.txt
if errorlevel 1 goto :falha

echo       Validando componentes essenciais...
"%PY%" -c "import fastapi,uvicorn,jinja2,multipart,polars,pyarrow,duckdb,apscheduler,openpyxl,pydantic,reportlab; print('      Todos os componentes foram validados.')"
if errorlevel 1 goto :falha

echo [3/5] Verificando gerador do executavel...
"%PY%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 "%PY%" -m pip install --disable-pip-version-check --prefer-binary pyinstaller==6.11.1
if errorlevel 1 goto :falha

echo [4/5] Limpando somente a compilacao anterior...
if exist "build" rmdir /s /q "build"
if exist "dist\Acompanhamento_Operacional" rmdir /s /q "dist\Acompanhamento_Operacional"

echo [5/5] Gerando executavel completo. Aguarde...
"%PY%" -m PyInstaller --noconfirm --clean Acompanhamento_Operacional.spec
if errorlevel 1 goto :falha

if not exist "dist\Acompanhamento_Operacional\Acompanhamento_Operacional.exe" goto :falha
echo       Configurando acesso pela rede local (porta TCP 8000)...
netsh advfirewall firewall show rule name="Acompanhamento Operacional - Porta 8000" >nul 2>&1
if errorlevel 1 netsh advfirewall firewall add rule name="Acompanhamento Operacional - Porta 8000" dir=in action=allow protocol=TCP localport=8000 profile=private >nul 2>&1
if errorlevel 1 (
  echo       AVISO: o Windows ou a politica da empresa exige autorizacao administrativa.
  echo       Execute CONFIGURAR_ACESSO_REDE.bat como administrador ou solicite a TI.
) else (
  echo       Acesso pela rede privada liberado com sucesso.
)
echo.
echo ============================================================
echo   EXECUTAVEL GERADO COM SUCESSO
echo ============================================================
echo Pasta final:
echo %CD%\dist\Acompanhamento_Operacional
echo.
echo Execute Acompanhamento_Operacional.exe dentro da pasta final.
pause
exit /b 0

:instalar_python
echo Python nao localizado. Verificando o instalador oficial do Windows...
where winget >nul 2>&1
if errorlevel 1 goto :sem_instalador_python
echo Instalando Python 3.12 para o usuario atual. Aguarde...
winget install --exact --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :sem_instalador_python
set "PYTHON_CMD="
where py >nul 2>&1 && set "PYTHON_CMD=py"
if not defined PYTHON_CMD (
  where python >nul 2>&1 && set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PYTHON_CMD goto :sem_instalador_python
goto :python_pronto

:python_pronto
if not exist ".venv\Scripts\python.exe" (
  echo [1/5] Criando ambiente isolado...
  "%PYTHON_CMD%" -m venv .venv
  if errorlevel 1 goto :falha
)
set "PY=.venv\Scripts\python.exe"
goto :dependencias

:sem_instalador_python
echo.
echo ERRO: o Windows nao permitiu instalar o Python automaticamente.
echo Solicite a TI a instalacao oficial do Python 3.12 ou execute em um computador autorizado.
pause
exit /b 1

:falha
echo.
echo ERRO: nao foi possivel gerar o executavel.
echo Revise as mensagens acima. Nenhum arquivo do Windows foi alterado.
pause
exit /b 1
