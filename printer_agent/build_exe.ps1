# Gera App de Impressão.exe (PowerShell)
# Executar na pasta printer_agent: .\build_exe.ps1

Set-Location $PSScriptRoot
$exeName = "App de Impressão.exe"
$exePath = Join-Path "dist" $exeName

Write-Host "Instalando dependencias se necessario..."
pip install -r requirements.txt -q

Write-Host ""
Write-Host "Gerando $exeName ..."
pyinstaller printer_agent.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERRO: PyInstaller falhou. Feche o app se ele estiver aberto e tente novamente." -ForegroundColor Red
    exit $LASTEXITCODE
}

if (Test-Path $exePath) {
    Write-Host ""
    Write-Host "OK: $exePath criado." -ForegroundColor Green
} else {
    $fallback = Get-ChildItem "dist\App de Impr*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($fallback) {
        Write-Host ""
        Write-Host ("OK: " + $fallback.FullName + " criado.") -ForegroundColor Green
        exit 0
    }
    Write-Host ""
    Write-Host "ERRO: Build falhou. Verifique as mensagens acima." -ForegroundColor Red
    Get-ChildItem dist\*.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name
    exit 1
}
