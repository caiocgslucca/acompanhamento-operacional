@echo off
setlocal EnableExtensions
title Configurar acesso de rede - Acompanhamento Operacional
echo ============================================================
echo   ACESSO NA REDE LOCAL - PORTA TCP 8000
echo ============================================================
echo.
echo Esta configuracao libera somente redes privadas do Windows.
netsh advfirewall firewall add rule name="Acompanhamento Operacional - Porta 8000" dir=in action=allow protocol=TCP localport=8000 profile=private
if errorlevel 1 (
  echo.
  echo O Windows bloqueou a alteracao. Clique com o botao direito neste
  echo arquivo e escolha "Executar como administrador" ou solicite a TI.
  pause
  exit /b 1
)
echo.
echo Acesso liberado. Nos outros dispositivos, use:
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /c:"IPv4"') do echo http://%%A:8000/carteira
pause
exit /b 0
