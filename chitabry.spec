# -*- mode: python ; coding: utf-8 -*-
# Chitabry, ricetta di compilazione.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# La guida viaggia dentro il pacchetto, nella cartella _internal, dove
# config.percorso_risorsa la cerca: fino alla 7.8.3 datas era vuoto e chi
# scaricava la release trovava la guida mancante (issue 50).

a = Analysis(
    ['Chitabry.py'],
    pathex=['e:\\git\\Mine\\GBUtils'],
    binaries=[],
    datas=[('ChitabryMan.txt', '.')],
    # requests e compagni servono al controllo aggiornamenti di GBUtils, che
    # li importa dentro la funzione: senza, l'eseguibile parte ma non riesce
    # a contattare GitHub. scipy.signal lo importa GBAudio in testa al file,
    # quindi PyInstaller lo trova da solo, ma dichiararlo non costa niente.
    hiddenimports=[
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'chardet',
        'scipy.signal',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Chitabry',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Chitabry',
)
