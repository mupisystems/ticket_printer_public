# Gera printer_agent.exe (PowerShell)
# Executar na pasta printer_agent: .\build_exe.ps1

Set-Location $PSScriptRoot

Write-Host "Instalando dependencias se necessario..."
pip install -r requirements.txt -q

Write-Host ""
Write-Host "Gerando printer_agent.exe ..."
pyinstaller printer_agent.spec

if (Test-Path "dist\printer_agent.exe") {
    Write-Host ""
    Write-Host "OK: dist\printer_agent.exe criado." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "ERRO: Build falhou. Verifique as mensagens acima." -ForegroundColor Red
    exit 1
}
