# Chitabry, i banchi di suoni: FluidSynth e i soundfont General MIDI, per il suono "banco".
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nato con la 9.10.0, dal collaudo di Gabriele del 7 ottobre 2026: l'armonica
# del sintetizzatore di Windows ha un vibrato che non si toglie, e un banco
# scelto fra quelli sul computer suona come si vuole. La ricerca dei banchi,
# il riconoscimento dei General MIDI e lo scaricamento di FluidSynth e di
# FluidR3 vengono da midi.py di MeTeOra, versione 1.67.4, copiati come ha
# chiesto Gabriele; la resa di una nota alla volta, per il mixer di Chitabry,
# e' di qui. Le note si rendono in memoria, come quelle sintetiche, e passano
# dal mixer insieme al battito del metronomo: nessuno sfasamento fra i due.

import contextlib
import ctypes
import hashlib
import io
import math
import os
import string
import struct
import tempfile
import threading
import urllib.request
import zipfile
from ctypes import wintypes

import numpy as np

import config

# I file dei banchi di suoni, e le cartelle che la ricerca non visita.
ESTENSIONI_DEI_BANCHI = (".sf2", ".sf3")
CARTELLE_DA_SALTARE = frozenset({"windows", "$recycle.bin", "system volume information", "recovery", "config.msi", "$windows.~bt", "$windows.~ws",
    "$winreagent", "node_modules", ".git", "__pycache__"})
_DISCO_FISSO = 3
# FluidSynth, la versione provata da MeTeOra il 3 ottobre 2026: lo zip
# ufficiale per Windows a 64 bit, la sua impronta, e le due DLL che servono.
FLUIDSYNTH_URL = "https://github.com/FluidSynth/fluidsynth/releases/download/v2.6.1/fluidsynth-v2.6.1-win10-x64-cpp11.zip"
FLUIDSYNTH_SHA256 = "fab7a2e4b85675b66970f97a39bbc239729c5e0f237198b5922a6a73cbc8677c"
FLUIDSYNTH_DLL = ("libfluidsynth-3.dll", "sndfile.dll")
# FluidR3 GM, il banco da scaricare quando nei dischi non ce n'e' uno:
# licenza MIT, le fonti in ordine di preferenza e la dimensione giusta.
FLUIDR3_NOME = "FluidR3_GM.sf2"
FLUIDR3_URL = (
    "https://github.com/pianobooster/fluid-soundfont/releases/download/v3.1/FluidR3_GM.sf2",
    "https://github.com/fhunleth/midi_synth/releases/download/v0.1.0/FluidR3_GM.sf2",
)
FLUIDR3_DIMENSIONE = 148398306
# I livelli dei messaggi di FluidSynth che si tacciono: avvisi, informazioni
# e messaggi di debug, che finirebbero sulla console.
_LIVELLI_TACIUTI = (2, 3, 4)
_PEZZO_DELLO_SCARICAMENTO = 1 << 20
# Il guadagno di FluidSynth: con il suo predefinito, 0.2, le note del banco
# SGM uscivano con un picco fra 0,02 e 0,09, troppo piano accanto agli altri
# suoni di Chitabry (misura del 7 ottobre 2026).
GUADAGNO = 1.0
# Il picco a cui si porta il DO centrale di ogni strumento del banco, prima
# del volume scelto: gli strumenti di un soundfont hanno livelli molto
# diversi, con il banco SGM l'armonica arrivava a 0,09 e la chitarra a 0,45, e
# senza pareggiarli il volume del banco andrebbe rifatto a ogni strumento.
PICCO_DI_RIFERIMENTO = 0.5
# Quanto dura la coda dopo il rilascio, cioe' quanto la nota si spegne da
# sola, e quanto si rende una nota tenuta sulla Tastiera: finche' il tasto e'
# giu' suona, e lasciandolo il mixer la chiude con la sua rampa.
CODA = 0.6
SECONDI_TENUTA = 8.0
# L'escursione predefinita del pitch bend, in semitoni: serve alle note che
# non cadono sul temperamento, come quelle di molte scale dell'archivio Scala.
ESCURSIONE_BEND = 2.0


def e_un_banco(percorso):
    """Vero se il file e' un banco di suoni SoundFont, sf2 o sf3:
    un RIFF di tipo sfbk."""
    try:
        with open(percorso, "rb") as f:
            testa = f.read(12)
    except OSError:
        return False
    return len(testa) == 12 and testa[:4] == b"RIFF" and testa[8:12] == b"sfbk"


def general_midi(percorso):
    """Vero se il banco ha tutti gli strumenti del General MIDI: i 128
    programmi nel banco 0 e una batteria nel banco 128. Lo dice l'elenco dei
    preset, il chunk phdr dentro la lista pdta; i campioni, che possono
    pesare un gigabyte, si saltano senza leggerli."""
    try:
        with open(percorso, "rb") as f:
            testa = f.read(12)
            if len(testa) < 12 or testa[:4] != b"RIFF" or testa[8:12] != b"sfbk":
                return False
            fine = 8 + struct.unpack("<I", testa[4:8])[0]
            while f.tell() + 8 <= fine:
                intestazione = f.read(8)
                if len(intestazione) < 8:
                    return False
                nome, dimensione = intestazione[:4], struct.unpack("<I", intestazione[4:])[0]
                if nome == b"LIST" and f.read(4) == b"pdta":
                    fine_della_lista = f.tell() + dimensione - 4
                    while f.tell() + 8 <= fine_della_lista:
                        sotto = f.read(8)
                        if len(sotto) < 8:
                            return False
                        nome_sotto, dimensione_sotto = sotto[:4], struct.unpack("<I", sotto[4:])[0]
                        if nome_sotto == b"phdr":
                            return _preset_general_midi(f.read(dimensione_sotto))
                        f.seek(dimensione_sotto + (dimensione_sotto & 1), 1)
                    return False
                if nome == b"LIST":
                    f.seek(dimensione - 4 + (dimensione & 1), 1)
                else:
                    f.seek(dimensione + (dimensione & 1), 1)
    except (OSError, struct.error):
        return False
    return False


def _preset_general_midi(dati):
    """Dai record del phdr, 38 byte l'uno con l'ultimo che chiude l'elenco:
    vero se ci sono i 128 programmi del banco 0 e una batteria nel 128."""
    programmi, batteria = set(), False
    for indice in range(len(dati) // 38 - 1):
        programma, banco = struct.unpack_from("<HH", dati, indice * 38 + 20)
        if banco == 0 and programma < 128:
            programmi.add(programma)
        elif banco == 128:
            batteria = True
    return len(programmi) == 128 and batteria


def dimensione_da_leggere(byte):
    """La dimensione di un banco in MB: con un decimale sotto i 10 MB."""
    mega = byte / 1_000_000
    return f"{mega:.1f} MB" if mega < 10 else f"{round(mega)} MB"


def dischi_fissi():
    """Le radici dei dischi fissi del computer, per esempio C:\\ ed E:\\."""
    kernel32 = ctypes.windll.kernel32
    maschera = kernel32.GetLogicalDrives()
    radici = []
    for indice, lettera in enumerate(string.ascii_uppercase):
        radice = f"{lettera}:\\"
        if maschera & (1 << indice) and kernel32.GetDriveTypeW(wintypes.LPCWSTR(radice)) == _DISCO_FISSO:
            radici.append(radice)
    return radici


def cerca_banchi(radici=None, avvisa=None, fermo=None):
    """I banchi General MIDI nelle radici, di partenza tutti i dischi fissi:
    lista di (percorso, dimensione in byte), in ordine di nome. I banchi di
    pochi strumenti, che suonerebbero con strumenti sbagliati o mancanti,
    restano fuori. avvisa(cartelle) arriva ogni tanto con le cartelle
    visitate fin li'; fermo(), se c'e' e torna vero, interrompe la ricerca.
    Le cartelle di sistema, nascoste o illeggibili si saltano, e anche quella
    dei file temporanei, dove i banchi sono di passaggio."""
    trovati = []
    visitate = 0
    temporanei = os.path.normcase(tempfile.gettempdir())
    for radice in radici if radici is not None else dischi_fissi():
        for cartella, sottocartelle, files in os.walk(radice, onerror=lambda _errore: None):
            if fermo is not None and fermo():
                return sorted(trovati, key=lambda t: os.path.basename(t[0]).casefold())
            visitate += 1
            if avvisa is not None and visitate % 2000 == 0:
                avvisa(visitate)
            sottocartelle[:] = [s for s in sottocartelle if s.casefold() not in CARTELLE_DA_SALTARE and not s.startswith("$")
                and os.path.normcase(os.path.join(cartella, s)) != temporanei]
            for nome in files:
                if nome.lower().endswith(ESTENSIONI_DEI_BANCHI):
                    percorso = os.path.join(cartella, nome)
                    if general_midi(percorso):
                        with contextlib.suppress(OSError):
                            trovati.append((percorso, os.path.getsize(percorso)))
    return sorted(trovati, key=lambda t: os.path.basename(t[0]).casefold())


def cartella_fluidsynth():
    """Dove Chitabry tiene FluidSynth scaricato: accanto ai suoi dati."""
    return os.path.join(config.cartella_dati(), "fluidsynth")


def cartella_dei_banchi():
    """Dove Chitabry mette i banchi che scarica."""
    return os.path.join(config.cartella_dati(), "banchi")


def fluidsynth_presente():
    return all(os.path.isfile(os.path.join(cartella_fluidsynth(), dll)) for dll in FLUIDSYNTH_DLL)


def _scarica(url, avanza=None):
    """I byte di un URL, a pezzi: avanza(scaricati, totale) a ogni pezzo,
    con totale None se il server non lo dice."""
    if not url.startswith("https://"):
        raise ValueError(f"solo indirizzi https: {url}")
    richiesta = urllib.request.Request(url, headers={"User-Agent": "Chitabry"})  # noqa: S310 - indirizzi https fissi, controllati sopra
    with urllib.request.urlopen(richiesta, timeout=60) as risposta:  # noqa: S310 - idem
        totale = int(risposta.headers.get("Content-Length") or 0) or None
        pezzi, scaricati = [], 0
        while pezzo := risposta.read(_PEZZO_DELLO_SCARICAMENTO):
            pezzi.append(pezzo)
            scaricati += len(pezzo)
            if avanza is not None:
                avanza(scaricati, totale)
    return b"".join(pezzi)


def scarica_fluidsynth(avanza=None):
    """Scarica FluidSynth, ne controlla l'impronta e ne mette le DLL nella
    sua cartella. Solleva OSError se qualcosa non va."""
    dati = _scarica(FLUIDSYNTH_URL, avanza)
    if hashlib.sha256(dati).hexdigest() != FLUIDSYNTH_SHA256:
        raise OSError("lo zip di FluidSynth scaricato non è quello atteso")
    cartella = cartella_fluidsynth()
    os.makedirs(cartella, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(dati)) as archivio:
        for nome in archivio.namelist():
            if os.path.basename(nome) in FLUIDSYNTH_DLL and "/bin/" in nome:
                with open(os.path.join(cartella, os.path.basename(nome)), "wb") as f:
                    f.write(archivio.read(nome))
    if not fluidsynth_presente():
        raise OSError("nello zip di FluidSynth mancano le DLL attese")


def scarica_fluidr3(avanza=None):
    """Scarica FluidR3 GM dalla prima fonte che risponde, controlla dimensione
    e intestazione, e restituisce il percorso del banco. OSError se nessuna
    fonte va."""
    cartella = cartella_dei_banchi()
    os.makedirs(cartella, exist_ok=True)
    destinazione = os.path.join(cartella, FLUIDR3_NOME)
    errori = []
    for url in FLUIDR3_URL:
        try:
            dati = _scarica(url, avanza)
        except OSError as e:
            errori.append(str(e))
            continue
        if len(dati) != FLUIDR3_DIMENSIONE or dati[:4] != b"RIFF" or dati[8:12] != b"sfbk":
            errori.append(f"{url}: il file non è FluidR3 GM")
            continue
        parziale = destinazione + ".parziale"
        with open(parziale, "wb") as f:
            f.write(dati)
        os.replace(parziale, destinazione)
        return destinazione
    raise OSError("; ".join(errori) or "nessuna fonte di FluidR3 GM risponde")


# La libreria di FluidSynth, caricata alla prima nota, e il synth con il
# banco attivo, uno solo: le note si rendono una alla volta, dal filo
# principale, e il lucchetto basta a tenerle in fila.
_LIBRERIA = []
_SYNTH = {}
_BLOCCO = threading.Lock()


def _fluid():
    if _LIBRERIA:
        return _LIBRERIA[0]
    dll = ctypes.CDLL(os.path.join(cartella_fluidsynth(), FLUIDSYNTH_DLL[0]))
    p = ctypes.c_void_p
    intero = ctypes.c_int
    firme = {
        "new_fluid_settings": (p, []),
        "fluid_settings_setnum": (intero, [p, ctypes.c_char_p, ctypes.c_double]),
        "fluid_settings_setint": (intero, [p, ctypes.c_char_p, intero]),
        "new_fluid_synth": (p, [p]),
        "fluid_synth_sfload": (intero, [p, ctypes.c_char_p, intero]),
        "fluid_synth_system_reset": (intero, [p]),
        "fluid_synth_program_change": (intero, [p, intero, intero]),
        "fluid_synth_pitch_bend": (intero, [p, intero, intero]),
        "fluid_synth_noteon": (intero, [p, intero, intero, intero]),
        "fluid_synth_noteoff": (intero, [p, intero, intero]),
        "fluid_synth_write_float": (intero, [p, intero, p, intero, intero, p, intero, intero]),
        "delete_fluid_synth": (None, [p]),
        "delete_fluid_settings": (None, [p]),
        "fluid_set_log_function": (p, [intero, p, p]),
    }
    for nome, (risultato, argomenti) in firme.items():
        funzione = getattr(dll, nome)
        funzione.restype, funzione.argtypes = risultato, argomenti
    for livello in _LIVELLI_TACIUTI:
        dll.fluid_set_log_function(livello, None, None)
    _LIBRERIA.append(dll)
    return dll


def _synth(banco, fs):
    """Il synth con il banco caricato, nuovo se il banco o la frequenza di
    campionamento sono cambiati. OSError se FluidSynth o il banco mancano."""
    if not fluidsynth_presente():
        raise OSError("FluidSynth non c'e': si scarica dalle impostazioni, alla voce del banco di suoni")
    if _SYNTH.get("chiave") == (banco, fs):
        return _SYNTH["synth"]
    fs_lib = _fluid()
    chiudi()
    impostazioni = fs_lib.new_fluid_settings()
    fs_lib.fluid_settings_setnum(impostazioni, b"synth.sample-rate", float(fs))
    fs_lib.fluid_settings_setnum(impostazioni, b"synth.gain", GUADAGNO)
    fs_lib.fluid_settings_setint(impostazioni, b"synth.lock-memory", 0)
    synth = fs_lib.new_fluid_synth(impostazioni)
    if not synth or fs_lib.fluid_synth_sfload(synth, banco.encode("utf-8"), 1) < 0:
        if synth:
            fs_lib.delete_fluid_synth(synth)
        fs_lib.delete_fluid_settings(impostazioni)
        raise OSError(f"il banco di suoni {banco} non si carica")
    _SYNTH.update(chiave=(banco, fs), synth=synth, impostazioni=impostazioni)
    return synth


def chiudi():
    """Chiude il synth del banco, se c'e': per quando il banco cambia."""
    _FATTORI.clear()
    if "synth" in _SYNTH and _LIBRERIA:
        _LIBRERIA[0].delete_fluid_synth(_SYNTH["synth"])
        _LIBRERIA[0].delete_fluid_settings(_SYNTH["impostazioni"])
    _SYNTH.clear()


def _scrivi(fs_lib, synth, campioni):
    sinistro = np.zeros(campioni, dtype=np.float32)
    destro = np.zeros(campioni, dtype=np.float32)
    if campioni > 0:
        fs_lib.fluid_synth_write_float(synth, campioni, sinistro.ctypes.data, 0, 1, destro.ctypes.data, 0, 1)
    return (sinistro + destro) / 2


def rendi_nota(banco, programma, frequenza, secondi, fs, velocita=100, coda=CODA):
    """Una nota del banco, in mono: tenuta per secondi, poi rilasciata con la
    sua coda. La frequenza si arrotonda alla nota MIDI e il resto si fa con
    il pitch bend, cosi' anche le note fuori dal temperamento suonano giuste.
    Solleva OSError se FluidSynth o il banco mancano."""
    if frequenza <= 0 or secondi <= 0:
        return np.zeros(0, dtype=np.float32)
    nota_esatta = 69 + 12 * math.log2(frequenza / 440.0)
    nota = round(nota_esatta)
    if not 0 <= nota <= 127:
        return np.zeros(0, dtype=np.float32)
    bend = round(8192 + (nota_esatta - nota) / ESCURSIONE_BEND * 8192)
    with _BLOCCO:
        synth = _synth(banco, fs)
        fs_lib = _fluid()
        fs_lib.fluid_synth_system_reset(synth)
        fs_lib.fluid_synth_program_change(synth, 0, int(programma))
        fs_lib.fluid_synth_pitch_bend(synth, 0, max(0, min(16383, bend)))
        fs_lib.fluid_synth_noteon(synth, 0, nota, int(velocita))
        tenuta = _scrivi(fs_lib, synth, int(secondi * fs))
        fs_lib.fluid_synth_noteoff(synth, 0, nota)
        rilascio = _scrivi(fs_lib, synth, int(coda * fs))
    return np.concatenate([tenuta, rilascio])


# Il fattore che pareggia ogni strumento, per banco, strumento e frequenza
# di campionamento: si misura una volta, alla prima nota
_FATTORI = {}


def fattore_dello_strumento(banco, programma, fs):
    """Quanto moltiplicare le note di uno strumento perche' il suo DO
    centrale arrivi al picco di riferimento. Le note fra loro tengono la
    dinamica che il banco da' loro."""
    chiave = (banco, programma, fs)
    if chiave not in _FATTORI:
        prova = rendi_nota(banco, programma, 261.63, 0.5, fs, coda=0.0)
        picco = float(np.abs(prova).max()) if prova.size else 0.0
        _FATTORI[chiave] = min(20.0, max(0.5, PICCO_DI_RIFERIMENTO / picco)) if picco > 1e-6 else 1.0
    return _FATTORI[chiave]


class RendererBanco:
    """Una nota del banco con l'interfaccia del NoteRenderer di GBAudio, cosi'
    che l'esercizio delle scale, la Tastiera e gli altri la trattino come una
    nota sintetica: set_params, render e render_tenuta. Il pan lo fa il
    mixer, quindi la nota e' mono, ripetuta sui due canali."""

    pan_l = 1.0

    def __init__(self, banco, programma, fs):
        self.banco = banco
        self.programma = programma
        self.fs = fs
        self.frequenza = 0.0
        self.durata = 1.0
        self.volume = 1.0

    def set_params(self, frequenza, durata, volume, _pan=0.0, **_altri):
        self.frequenza, self.durata, self.volume = frequenza, durata, volume

    def render(self):
        fattore = fattore_dello_strumento(self.banco, self.programma, self.fs)
        mono = rendi_nota(self.banco, self.programma, self.frequenza, self.durata, self.fs) * (fattore * self.volume)
        return np.column_stack([mono, mono]).astype(np.float32)

    def render_tenuta(self):
        """La nota tenuta della Tastiera: otto secondi senza rilascio, che il
        mixer chiude con la sua rampa quando il tasto si lascia."""
        fattore = fattore_dello_strumento(self.banco, self.programma, self.fs)
        mono = rendi_nota(self.banco, self.programma, self.frequenza, SECONDI_TENUTA, self.fs, coda=0.0) * (fattore * self.volume)
        return mono.astype(np.float32), None
