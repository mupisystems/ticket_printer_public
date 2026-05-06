@echo off
REM Gera printer_agent.exe (executar na pasta printer_agent)
REM Requer: pip install -r requirements.txt

cd /d "%~dp0"

echo Instalando dependencias se necessario...
pip install -r requirements.txt -q

set ICON_SRC=
if exist "tray_icon.png" set ICON_SRC=tray_icon.png
if not defined ICON_SRC if exist "logo.png" set ICON_SRC=logo.png

if defined ICON_SRC (
    echo Gerando printer_agent.ico a partir de %ICON_SRC% ...
    python -c "from PIL import Image; img=Image.open(r'%ICON_SRC%').convert('RGBA'); img.save('printer_agent.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
)

if exist "dist\printer_agent.exe" del /f /q "dist\printer_agent.exe" >nul 2>nul

echo.
echo Gerando printer_agent.exe ...
pyinstaller --clean --noconfirm printer_agent.spec

if exist "dist\printer_agent.exe" (
    echo.
    echo OK: dist\printer_agent.exe criado.
) else (
    echo.
    echo ERRO: Build falhou. Verifique as mensagens acima.
    exit /b 1
)
