# Gera printer_agent.exe (PowerShell)
# Executar na pasta printer_agent: .\build_exe.ps1

Set-Location $PSScriptRoot

Write-Host "Instalando dependencias se necessario..."
pip install -r requirements.txt -q

$iconSource = $null
if (Test-Path "tray_icon.png") {
    $iconSource = "tray_icon.png"
} elseif (Test-Path "logo.png") {
    $iconSource = "logo.png"
}

if ($iconSource) {
    Write-Host "Gerando printer_agent.ico a partir de $iconSource ..."
    python -c "from PIL import Image; img=Image.open(r'$iconSource').convert('RGBA'); img.save('printer_agent.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
}

if (Test-Path "dist\printer_agent.exe") {
    Remove-Item "dist\printer_agent.exe" -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Gerando printer_agent.exe ..."
pyinstaller --clean --noconfirm printer_agent.spec

if (Test-Path "dist\printer_agent.exe") {
    Write-Host ""
    Write-Host "OK: dist\printer_agent.exe criado." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "ERRO: Build falhou. Verifique as mensagens acima." -ForegroundColor Red
    exit 1
}
