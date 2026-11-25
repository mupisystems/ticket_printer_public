@echo off
REM Gera o instalador do Agente de Impressao (Inno Setup 6).
REM Executar na pasta printer_agent:
REM   build_installer.bat            reaproveita dist\AgenteImpressao se ja existir
REM   build_installer.bat --rebuild  roda build_exe.bat antes (novo build ONEDIR)
REM Saida: dist\installer\AgenteImpressao-Setup-<versao>.exe
REM Requer: Python com Pillow e Inno Setup 6 (ISCC.exe).
REM Opcional: variavel ISCC_EXE com o caminho do ISCC.exe;
REM           installer\MicrosoftEdgeWebview2Setup.exe para embutir o WebView2.

setlocal
cd /d "%~dp0"

set "REBUILD="
:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--rebuild" (
    set "REBUILD=1"
    shift
    goto parse_args
)
echo ERRO: argumento desconhecido: %~1
echo Uso: build_installer.bat [--rebuild]
exit /b 2
:args_done

set "DIST_DIR=dist\AgenteImpressao"
set "DIST_EXE=%DIST_DIR%\AgenteImpressao.exe"

REM ---- 1. Build ONEDIR (PyInstaller) ------------------------------------------
if defined REBUILD goto do_build
if not exist "%DIST_EXE%" goto do_build
echo Usando build existente: %DIST_DIR%
goto build_ready

:do_build
echo.
echo ==^> Gerando o executavel (build_exe.bat)...
call "%~dp0build_exe.bat"
if errorlevel 1 goto err_build
cd /d "%~dp0"

:build_ready
if not exist "%DIST_EXE%" goto err_dist

REM ---- 2. Localiza o ISCC.exe -------------------------------------------------
if defined ISCC_EXE if not exist "%ISCC_EXE%" goto err_iscc_var
if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE for /f "delims=" %%i in ('where ISCC.exe 2^>nul') do if not defined ISCC_EXE set "ISCC_EXE=%%i"
if not defined ISCC_EXE goto err_iscc

REM ---- 3. Imagens do assistente -----------------------------------------------
echo.
echo ==^> Gerando imagens do assistente...
python installer\make_wizard_images.py
if errorlevel 1 goto err_images

REM ---- 4. Versao --------------------------------------------------------------
set "APP_VERSION="
for /f "delims=" %%v in ('python -c "from config import APP_VERSION; print(APP_VERSION)"') do set "APP_VERSION=%%v"
if not defined APP_VERSION goto err_version

REM ---- 5. Compila -------------------------------------------------------------
echo.
if exist "installer\MicrosoftEdgeWebview2Setup.exe" (
    echo WebView2: bootstrapper sera embutido no instalador.
) else (
    echo WebView2: bootstrapper ausente - o instalador so avisara se o runtime faltar.
)
echo ==^> Compilando o instalador %APP_VERSION% com "%ISCC_EXE%"...
"%ISCC_EXE%" /Qp "/DAppVersion=%APP_VERSION%" "installer\agente_impressao.iss"
if errorlevel 1 goto err_compile

echo.
echo OK: dist\installer\AgenteImpressao-Setup-%APP_VERSION%.exe
exit /b 0

REM ---- Erros ------------------------------------------------------------------
:err_build
echo.
echo ERRO: build_exe.bat falhou. Veja as mensagens acima.
exit /b 1

:err_dist
echo.
echo ERRO: build ONEDIR nao encontrado: "%CD%\%DIST_EXE%"
echo       Gere com: build_installer.bat --rebuild   (ou build_exe.bat)
exit /b 1

:err_iscc_var
echo.
echo ERRO: ISCC_EXE aponta para um arquivo inexistente: "%ISCC_EXE%"
exit /b 1

:err_iscc
echo.
echo ERRO: Inno Setup 6 (ISCC.exe) nao encontrado.
echo       Instale em https://jrsoftware.org/isdl.php ou defina ISCC_EXE com o caminho do ISCC.exe.
exit /b 1

:err_images
echo.
echo ERRO: falha ao gerar as imagens do assistente (Python + Pillow instalados?).
exit /b 1

:err_version
echo.
echo ERRO: nao foi possivel ler APP_VERSION de config.py.
exit /b 1

:err_compile
echo.
echo ERRO: o Inno Setup falhou ao compilar installer\agente_impressao.iss. Veja as mensagens acima.
exit /b 1
