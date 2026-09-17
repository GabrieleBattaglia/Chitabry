# Chitabry, hook di avvio per il pacchetto compilato.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5, modalità auto).
# Nato il 17 settembre 2026, quando matplotlib e' uscito dal pacchetto.
"""music21 controlla all'avvio se matplotlib c'e', e se manca stampa tre righe
che invitano a installarlo, con tanto di indirizzo web. Dal 17 settembre 2026
matplotlib non entra piu' nel pacchetto: serve solo ai grafici di music21, che
Chitabry non disegna, e si portava dietro i backend Tk e Qt per una sessantina
di megabyte di roba mai usata. L'avviso pero' resterebbe, e tre righe di rumore
all'avvio, per giunta con un URL dentro, sono tre righe che lo screen reader
legge a chi non ha chiesto niente.
Qui music21 viene importata una volta sola con le due uscite deviate: l'avviso
finisce in un cestino di memoria e i moduli del programma, quando la importano,
la trovano gia' caricata e zitta. Se l'import fallisse, il silenzio non
nasconde il guasto: se ne accorge il programma, che la importa subito dopo e
mostra l'errore vero.
Questo file viene eseguito da PyInstaller prima del programma, cioe' prima di
qualunque import di Chitabry; da sorgente non viene eseguito, e li' l'avviso
non compare perche' matplotlib e' installato.
"""
import contextlib
import io

with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()), contextlib.suppress(ImportError):
    import music21  # noqa: F401
