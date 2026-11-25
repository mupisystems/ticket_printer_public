# PyInstaller spec do Agente de Impressão — build ONEDIR (pasta), usado pelo instalador.
# Gerar: pyinstaller --clean --noconfirm printer_agent.spec   (na pasta printer_agent)
# Saída: dist\AgenteImpressao\AgenteImpressao.exe (+ _internal\)
# Instalador: build_installer.bat (Inno Setup) empacota essa pasta.

import os
import sys

from PyInstaller.utils.hooks import collect_data_files


def _resolve_windows_icon(spec_dir: str) -> str | None:
    """Define o icone do .exe para aparecer no Explorer/atalhos do Windows."""
    ico_candidates = ("printer_agent.ico", "tray_icon.ico", "logo.ico")
    for name in ico_candidates:
        path = os.path.join(spec_dir, name)
        if os.path.isfile(path):
            return path

    png_candidates = ("tray_icon.png", "logo.png")
    for name in png_candidates:
        png_path = os.path.join(spec_dir, name)
        if not os.path.isfile(png_path):
            continue
        try:
            from PIL import Image

            out_dir = os.path.join(spec_dir, "build")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, "_generated_app_icon.ico")
            img = Image.open(png_path).convert("RGBA")
            img.save(out_path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            return out_path
        except Exception:
            return None

    return None


# PyInstaller define SPECPATH = pasta do .spec quando executa o spec
spec_dir = SPECPATH
exe_icon = _resolve_windows_icon(spec_dir)

sys.path.insert(0, spec_dir)
APP_NAME = 'AgenteImpressao'   # nome fixo: atalhos e inicialização automática apontam para ele

block_cipher = None

# Assets: tray_icon.png/logo.png (bandeja) e a interface web (ui/)
datas = []
for name in ('logo.png', 'tray_icon.png'):
    path = os.path.join(spec_dir, name)
    if os.path.isfile(path):
        datas.append((path, '.'))
datas.append((os.path.join(spec_dir, 'ui'), 'ui'))

# pywebview carrega seus scripts (webview/js/*.js) em tempo de execução; o hook
# padrão só copia as DLLs do WebView2 (webview/lib).
datas += collect_data_files('webview', subdir='js')

# python-escpos precisa de capabilities.json no pacote (importlib_resources)
try:
    import escpos
    escpos_dir = os.path.dirname(escpos.__file__)
    cap_json = os.path.join(escpos_dir, 'capabilities.json')
    if os.path.isfile(cap_json):
        datas.append((cap_json, 'escpos'))
except Exception:
    pass

a = Analysis(
    [os.path.join(spec_dir, 'main.py')],
    pathex=[spec_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'config',
        'printer_service',
        'websocket_client',
        'tray',
        'app_window',
        'ticket_formatter',
        'ticket_preview',
        'ticket_logo',
        'log_buffer',
        'windows_startup',
        'pystray._win32',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'clr',
        'win32print',
        'win32ui',
        'win32crypt',
        'win32clipboard',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', '_tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX desativado: compressão UPX aumenta falsos positivos em AVs
    console=False,  # sem janela de console (app de bandeja)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
    version=os.path.join(spec_dir, 'version_info.txt'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
