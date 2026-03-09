@echo off
REM Gera App de Impressão.exe (executar na pasta printer_agent)
REM Requer: pip install -r requirements.txt

set "EXE_NAME=App de Impressão.exe"
set "EXE_PATH=dist\%EXE_NAME%"

cd /d "%~dp0"

echo Instalando dependencias se necessario...
pip install -r requirements.txt -q

echo.
echo Gerando %EXE_NAME% ...
pyinstaller printer_agent.spec
if errorlevel 1 (
    echo.
    echo ERRO: PyInstaller falhou. Feche o app se ele estiver aberto e tente novamente.
    exit /b 1
)

if exist "%EXE_PATH%" (
    echo.
    echo OK: %EXE_PATH% criado.
) else (
    REM Fallback robusto para evitar falso negativo com encoding/acentuacao no cmd
    for %%F in ("dist\App de Impr*.exe") do (
        if exist "%%~fF" (
            echo.
            echo OK: %%~fF criado.
            exit /b 0
        )
    )
    echo.
    echo ERRO: Build falhou. Verifique as mensagens acima.
    dir /b dist\*.exe 2>nul
    exit /b 1
)
