# PyInstaller spec para App de Impressão.exe
# Gerar: pyinstaller printer_agent.spec
# (executar na pasta printer_agent)

import os

# PyInstaller define SPECPATH = pasta do .spec quando executa o spec
spec_dir = SPECPATH


def _get_exe_icon_path() -> str | None:
    ico_path = os.path.join(spec_dir, 'build', 'tray_app.ico')
    tray_icon_path = os.path.join(spec_dir, 'tray_icon.png')
    if not os.path.isfile(tray_icon_path):
        fallback_ico_path = os.path.join(spec_dir, 'app.ico')
        return fallback_ico_path if os.path.isfile(fallback_ico_path) else None

    try:
        from PIL import Image

        os.makedirs(os.path.dirname(ico_path), exist_ok=True)
        img = Image.open(tray_icon_path).convert('RGBA')
        img.save(ico_path, format='ICO', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        return ico_path if os.path.isfile(ico_path) else None
    except Exception:
        fallback_ico_path = os.path.join(spec_dir, 'app.ico')
        return fallback_ico_path if os.path.isfile(fallback_ico_path) else None

block_cipher = None
exe_icon_path = _get_exe_icon_path()

# Ícones e assets: logo.png (cabeçalho), tray_icon.png (bandeja)
datas = []
for name in ('logo.png', 'tray_icon.png', 'app.ico'):
    path = os.path.join(spec_dir, name)
    if os.path.isfile(path):
        datas.append((path, '.'))

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
        'config_window',
        'ticket_formatter',
        'pystray._win32',
        'PIL._tkinter_finder',
        'win32print',
        'win32ui',
        'win32crypt',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='App de Impressão',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # sem janela de console (app de bandeja)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon_path,
)
