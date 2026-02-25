# PyInstaller spec para printer_agent.exe
# Gerar: pyinstaller printer_agent.spec
# (executar na pasta printer_agent)

import os

# PyInstaller define SPECPATH = pasta do .spec quando executa o spec
spec_dir = SPECPATH

block_cipher = None

# Ícones e assets: logo.png (cabeçalho), tray_icon.png (bandeja)
datas = []
for name in ('logo.png', 'tray_icon.png'):
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
    name='printer_agent',
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
)
