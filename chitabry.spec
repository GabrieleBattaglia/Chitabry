# -*- mode: python ; coding: utf-8 -*-
# Chitabry, ricetta di compilazione.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# La guida viaggia dentro il pacchetto, nella cartella _internal, dove
# config.percorso_risorsa la cerca: fino alla 7.8.3 datas era vuoto e chi
# scaricava la release trovava la guida mancante (issue 50).
# Con la guida viaggia l'archivio Scala di music21, quasi quattromila file
# .scl che PyInstaller non vede da solo: senza, il catalogo delle scale del
# pacchetto aveva 27 voci invece di centinaia, e nessuno se n'era accorto
# perche' da sorgente si trovano comunque. Si compila con l'interprete che
# ha le librerie: python -m PyInstaller --noconfirm chitabry.spec.
import os

from PyInstaller.utils.hooks import collect_data_files

# Il percorso di GBUtils si ricava dalla posizione di questo file, cosi' la
# compilazione riesce anche su una macchina dove i repository stanno altrove.
GBUTILS_DIR = os.path.abspath(os.path.join(SPECPATH, '..', 'GBUtils'))

a = Analysis(
    ['Chitabry.py'],
    pathex=[GBUTILS_DIR],
    binaries=[],
    datas=[('ChitabryMan.txt', '.')] + collect_data_files('music21', subdir=os.path.join('scale', 'scala', 'scl')),
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
    # L'hook gira prima del programma e importa music21 zitta: senza
    # matplotlib nel pacchetto, all'avvio stamperebbe tre righe di invito
    # a installarlo, che lo screen reader leggerebbe a ogni avvio.
    runtime_hooks=['hook_music21.py'],
    # Peso morto: matplotlib arriva dietro alle librerie di calcolo e si
    # porta i backend Tk e Qt, che qui non servono a nessuno perche' il
    # programma e' a console e non disegna niente. numpy e scipy invece
    # restano: sono le librerie con cui Acusticator genera i suoni.
    excludes=[
        'matplotlib', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'tkinter',
        'pandas', 'IPython', 'jupyter', 'notebook',
    ],
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
