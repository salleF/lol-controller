# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec para gerar um executavel standalone (.exe) do LoL Controller.
#
# Uso:
#   pip install pyinstaller
#   pyinstaller lolcontroller.spec
#
# O resultado fica em dist/LoLController.exe (onefile, sem console). Assim o
# usuario final nao precisa instalar Python nem rodar comandos no terminal —
# basta dar duplo clique (ou "Executar como administrador", ver README).

import os
from PyInstaller.utils.hooks import collect_data_files

# customtkinter carrega temas/assets (JSON, fontes) em runtime; sem coletar
# esses dados o app abre com erro de tema ausente quando congelado.
datas = collect_data_files("customtkinter")

# icon.ico e opcional (a GUI so o usa se existir). So o embarca se estiver
# presente no repo, para o mesmo spec funcionar com ou sem o icone.
_icon = "icon.ico" if os.path.exists("icon.ico") else None
if _icon:
    datas.append((_icon, "."))

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="LoLController",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # app de GUI: sem janela de console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)
