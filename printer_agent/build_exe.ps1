# Gera o build ONEDIR do Agente de Impressao (PowerShell).
# Executar na pasta printer_agent: .\build_exe.ps1            -> dist\AgenteImpressao\
#                                   .\build_exe.ps1 -Installer -> tambem gera o instalador
param([switch]$Installer)

Set-Location $PSScriptRoot

if ($Installer) {
    & "$PSScriptRoot\build_installer.bat" --rebuild
} else {
    & "$PSScriptRoot\build_exe.bat"
}
exit $LASTEXITCODE
