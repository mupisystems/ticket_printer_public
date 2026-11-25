@echo off
REM Gera o build ONEDIR do Agente de Impressao: dist\AgenteImpressao\AgenteImpressao.exe
REM Executar na pasta printer_agent. Para gerar o instalador use build_installer.bat.
REM Requer: pip install -r requirements.txt

setlocal
cd /d "%~dp0"

echo Instalando dependencias se necessario...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ERRO: falha ao instalar as dependencias.
    exit /b 1
)

set "ICON_SRC="
if exist "tray_icon.png" set "ICON_SRC=tray_icon.png"
if not defined ICON_SRC if exist "logo.png" set "ICON_SRC=logo.png"

if defined ICON_SRC (
    echo Gerando printer_agent.ico a partir de %ICON_SRC% ...
    python -c "from PIL import Image; img=Image.open(r'%ICON_SRC%').convert('RGBA'); img.save('printer_agent.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
)

REM -- Encerra o agente se estiver rodando (evita PermissionError no build) ---
echo Encerrando instancias em execucao...
taskkill /f /im "AgenteImpressao.exe" >nul 2>nul
ping -n 3 127.0.0.1 >nul

REM -- Remove o build anterior (com nova tentativa: antivirus/OneDrive podem segurar arquivos)
if exist "dist\AgenteImpressao" (
    rmdir /s /q "dist\AgenteImpressao" >nul 2>nul
    if exist "dist\AgenteImpressao" (
        echo Aguardando antivirus/OneDrive liberar arquivos...
        ping -n 6 127.0.0.1 >nul
        rmdir /s /q "dist\AgenteImpressao" >nul 2>nul
    )
)

echo.
echo Gerando dist\AgenteImpressao ...
pyinstaller --clean --noconfirm printer_agent.spec
if errorlevel 1 goto failed
if not exist "dist\AgenteImpressao\AgenteImpressao.exe" goto failed

echo.
echo OK: dist\AgenteImpressao\AgenteImpressao.exe criado.
echo Para gerar o instalador: build_installer.bat
exit /b 0

:failed
echo.
echo ERRO: Build falhou. Verifique as mensagens acima.
exit /b 1
