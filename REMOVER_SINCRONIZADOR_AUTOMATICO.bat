@echo off
setlocal
set "LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Acompanhamento Operacional Sync.lnk"
if exist "%LINK%" del /q "%LINK%"
echo Inicializacao automatica removida. O processo atual encerra no proximo reinicio.
pause
