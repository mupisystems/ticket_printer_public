@echo off
REM Gera "App de Impressao - Meu Atendimento Virtual X.X.X.exe"
REM Executar na pasta printer_agent
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

for /f "delims=" %%v in ('python -c "from config import APP_VERSION; print(APP_VERSION)"') do set APP_VERSION=%%v
set EXE_NAME=App de Impressao - Meu Atendimento Virtual %APP_VERSION%

REM ── Encerra o exe se estiver rodando (evita PermissionError no build) ───────
echo Encerrando instancias em execucao...
taskkill /f /im "%EXE_NAME%.exe" >nul 2>nul
taskkill /f /im "Agente-de-Impressao.exe" >nul 2>nul
timeout /t 2 /nobreak >nul

REM ── Remove exe anterior com retry (Kaspersky/OneDrive podem demorar a soltar)
if exist "dist\%EXE_NAME%.exe" (
    del /f /q "dist\%EXE_NAME%.exe" >nul 2>nul
    if exist "dist\%EXE_NAME%.exe" (
        echo Aguardando antivirus/OneDrive liberar arquivo...
        timeout /t 5 /nobreak >nul
        del /f /q "dist\%EXE_NAME%.exe" >nul 2>nul
    )
)

echo.
echo Gerando "%EXE_NAME%.exe" ...
pyinstaller --clean --noconfirm printer_agent.spec

if not exist "dist\%EXE_NAME%.exe" (
    echo.
    echo ERRO: Build falhou. Verifique as mensagens acima.
    exit /b 1
)

echo.
echo OK: dist\%EXE_NAME%.exe criado.

REM ── Resolve pasta principal (pai de printer_agent) ─────────────────────────
for %%i in ("%~dp0..") do set PARENT_DIR=%%~fi

REM ── Remove versoes antigas do exe na pasta principal ───────────────────────
echo.
echo Limpando versoes antigas na pasta principal...
for %%f in ("%PARENT_DIR%\App de Impressao - Meu Atendimento Virtual *.exe") do (
    if /i not "%%~nxf"=="%EXE_NAME%.exe" (
        del /f /q "%%f" >nul 2>nul
        echo   Removido: %%~nxf
    )
)
if exist "%PARENT_DIR%\Agente-de-Impressao.exe" (
    del /f /q "%PARENT_DIR%\Agente-de-Impressao.exe" >nul 2>nul
    echo   Removido: Agente-de-Impressao.exe (nome antigo)
)

REM ── Copia exe para pasta principal ────────────────────────────────────────
echo.
echo Copiando para pasta principal...
copy /y "dist\%EXE_NAME%.exe" "%PARENT_DIR%\%EXE_NAME%.exe" >nul 2>nul
if exist "%PARENT_DIR%\%EXE_NAME%.exe" (
    echo OK: "%PARENT_DIR%\%EXE_NAME%.exe"
) else (
    echo AVISO: Falha ao copiar para %PARENT_DIR%
)

REM ── Atualiza .gitignore na pasta principal ─────────────────────────────────
set GI=%PARENT_DIR%\.gitignore
set TMP_GI=%TEMP%\_gi_%RANDOM%.txt

if not exist "%GI%" (
    echo AVISO: .gitignore nao encontrado em %PARENT_DIR%
    goto :done
)

echo.
echo Atualizando .gitignore...
findstr /v /c:"!Agente-de-Impressao.exe" /c:"!App de Impressao - Meu Atendimento Virtual" "%GI%" > "%TMP_GI%"
echo !App de Impressao - Meu Atendimento Virtual %APP_VERSION%.exe >> "%TMP_GI%"
move /y "%TMP_GI%" "%GI%" >nul 2>nul
echo OK: .gitignore atualizado com "!%EXE_NAME%.exe"

:done
echo.
echo Build concluido!
