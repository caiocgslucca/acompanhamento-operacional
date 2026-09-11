@echo off
setlocal
cd /d "%~dp0"
if not exist "sync_config.json" (
  echo ERRO: execute primeiro CONFIGURAR_SINCRONIZADOR.bat.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo ERRO: ambiente Python nao preparado.
  pause
  exit /b 1
)
set "LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Acompanhamento Operacional Sync.lnk"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut($env:LINK); $s.TargetPath='wscript.exe'; $s.Arguments='""%CD%\sync_background.vbs""'; $s.WorkingDirectory='%CD%'; $s.Description='Sincronizador Acompanhamento Operacional'; $s.Save()"
if errorlevel 1 (
  echo ERRO: nao foi possivel ativar a inicializacao automatica.
  pause
  exit /b 1
)
start "" wscript.exe "%CD%\sync_background.vbs"
echo Sincronizador automatico ativado para este usuario do Windows.
exit /b 0
