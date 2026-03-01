@echo off
REM Gera printer_agent.exe (executar na pasta printer_agent)
REM Requer: pip install -r requirements.txt

cd /d "%~dp0"

echo Instalando dependencias se necessario...
pip install -r requirements.txt -q

echo.
echo Gerando printer_agent.exe ...
pyinstaller printer_agent.spec

if exist "dist\printer_agent.exe" (
    echo.
    echo OK: dist\printer_agent.exe criado.
) else (
    echo.
    echo ERRO: Build falhou. Verifique as mensagens acima.
    exit /b 1
)
