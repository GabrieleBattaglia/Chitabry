# Chitabry
Un tentativo per migliorare il mio studio della chitarra e un'idea per gestire una raccolta di accordi

## Se esegui lo script Python, assicurati di avere GBUtils.py nella stessa cartella. Puoi scaricarlo dall'omonimo progetto su GitHub.

# Benvenuti nel manuale, istruzioni per l'uso, di Chitabry.
L'ultima revisione di questo documento e' la numero 2, di mercoledi' 11 marzo 2020.
A cura di Gabriele Battaglia.

Chitabry e' un software ideato e realizzato dal sottoscritto, per aiutare tutti coloro che lo desiderano, ad approcciarsi al meraviglioso mondo della chitarra. L'intento sarebbe quello di creare un compagno virtuale, sempre pronto e al vostro fianco mentre vi esercitate con lo strumento e ne imparate trucchi e segreti.
Ogni segnalazione di bug, malfunzionamenti ed errori, nel programma o in questo manuale, sara' gradita, scrivetemi una e-mail ad iz4apu@libero.it descrivendo con la massima precisione possibile cio' che riscontrate ed io cerchero' di aiutarvi come posso. Chiunque e' autorizzato ed incoraggiato a distribuire questo software cosi' com'e', senza garanzie e gratuitamente.
E' vietato modificarne il codice senza espressa autorizzazione del sottoscritto. Se vi piace Chitabry, fatemelo sapere scrivendomi 2 righe. Grazie.
Il sottoscritto non puo' essere ritenuto responsabile per alcun danno derivato dall'uso improprio di questo software.
Gabriele Battaglia.

Chitabry puo' essere compilato sia per Windows che per MacOS, dovrebbe girare anche sotto Linux ma non ho la possibilita' di testarlo di persona.

Come installare Chitabry.
L'installazione e' un processo molto semplice. Salvate Chitabry.exe e Chitabryman.txt in una cartella di vostra scelta, qualsiasi posizione va bene, comprese penne USB e dischi esterni. Poi lanciate l'eseguibile .exe, oppure aprite una finestra terminale nella cartella dove avete incollato l'eseguibile, digitate chitabry e premete invio.
Alla conclusione del programma, la finestra si chiude automaticamente; se avevate aperto un terminale o prompt dei comandi, dovete chiuderlo digitando exit e battendo invio.
Prima di lanciare il software, vi consiglio di leggere questo manuale.

Il menu' principale.
Vediamo le scelte disponibili nel menu' principale e come funzionano.
Partiamo col dire che Chitabry e' un'applicazione a console. Questo significa che non possiede una finestra con menu', pulsanti, campi di editazione ed altri controlli a cui si accede con tab e shift+tab come avviene nelle piu' comuni applicazioni. Da console significa che Chitabry apre una finestra singola, tipicamente a sfondo scuro, su cui compaiono i messaggi che il programma desidera far leggere all'utente. In fondo a questa finestra, sull'ultima riga c'e' un cursore, un trattino lampeggiante che indica dove compariranno le lettere che l'utente scrivera'. In questo modo, l'user, cioe' noi che usiamo l'App, dobbiamo scrivere dei comandi, quindi premere invio e Chitabry si incarichera' di fornirci le risposte appropriate.
Percio', noi scriveremo un comando e, solo dopo aver premuto invio, potremo ascoltare, o leggere, la risposta del programma.
Vediamo il primo comando utile. Digitando una "m", di Milano, e premendo invio, Chitabry ci dara' la lista di tutti i comandi disponibili, cosi' se non ci ricordiamo cosa fare, la "m" potra' sempre venirci in soccorso.
Un secondo comando molto importante e' rappresentato dalla semplice pressione del tasto invio, cosi', senza scrivere niente, come se volessimo inviare un comando vuoto, indica a Chitabry che desideriamo chiuderlo; il programma infatti, non appena riceve invio senza che si sia digitato nulla, termina la propria esecuzione e rilascia il controllo a Windows.
Digitando la lettera "I" piu' invio, l'App mostrera' questa guida. Se vi viene piu' comodo, potrete leggervela col vostro editor di testi preferito, caricando il file Chitabryman.txt salvato assieme a chitabry.exe.
Corda.Tasto, abbreviato nel menu' come C.T, indica a Chitabry che vogliamo sapere quale nota si trova in una determinata posizione sul manico della chitarra.
Il comando va scritto inserendo il numero della corda, da 6, il MI grosso, ad 1, il MI cantino, seguito da un punto "." e poi dal numero del tasto.
Nota: il tasto 0, cioe' nessun tasto premuto, indica la corda vuota, o libera. Percio', se vogliamo sapere a quale nota corrisponde il tasto 3 della corda 6, dovremo semplicemente scrivere: 6.3 seguito da invio e Chitabry docilmente ci rispondera':
Sulla corda 6, tasto 3, si trova la nota: SOL2
Quel, 2, dopo la nota SOL, specifica l'ottava di appartenenza: sul manico infatti, si trovano altri SOL che appartengono ad altre ottave.
Allo stesso modo potremmo scrivere 3.13 e scoprire che, sulla terza corda, il tasto 13 produce la nota SOL#4. Che significa "#4"? Il 4 e' sempre l'ottava di appartenenza, questa volta 2 ottave sopra al nostro SOL di corda 6 tasto 3, mentre il simbolo "#" indica una nota diesis, cioe' in questo caso a meta' fra il SOL ed il LA.
Nota: Chitabry non conosce i bemolle, tutte le note non naturali vengono indicate come diesis "#".
NomeNota. Ed ecco la funzione contraria rispetto a Corda.Tasto. Grazie a NomeNota, potremo dire una qualsiasi nota a Chitabry e il programma ci dara' la, o le, posizioni in cui questa nota si trova, sul manico della chitarra.
Ad esempio potremmo voler conoscere la posizione di tutti i RE. Ci bastera' lanciare Chitabry e scrivere semplicemente RE, seguito da invio. Il programma rispondera':
Nota RE trovata nelle seguenti posizioni sul manico:
Corda 6, tasti: 10 11
Corda 5, tasti: 5 6 17 18
Corda 4, tasti: 0 1 12 13
Corda 3, tasti: 7 8 19 20
Corda 2, tasti: 3 4 15 16
Corda 1, tasti: 10 11
A questo punto sarebbe lecito chiedersi, perche' Chitabry individua delle coppie di tasti vicini, ad esempio i tasti 3 e 4 in corda 2? La risposta e' che anche un RE diesis e', in fondo, sempre un RE, e quindi Chitabry lo riporta fedelmente. Il tasto 4 di corda 2 e', per l'appunto, un RE diesis. Nel caso volessimo cercare solo i RE diesis ci bastera' scrivere RE#.
E se desiderassimo conoscere la posizione di una nota appartenente ad un'ottava specifica? Semplice: bastera' scriverla dopo la nota, ad esempio MI3, oppure FA4, DO5 eccetera.

Le SCALE.
Questa funzione serve ad individuare le note appartenenti ad una data scala e ad indicarne le relative posizioni sul manico. Sara' possibile scegliere il tipo di scala, al momento della stesura di questo manuale, Chitabry ne conosce 6, dopo di che' viene chiesta la nota tonica, quella da cui parte ed arriva la scala, quindi, per finire, i limiti di manico entro cui cercare le note.
Per scegliere la tipologia di scala, vi sara' sufficiente digitarne parte del nome: andra' benissimo ad esempio, "melo" per melodica, o arm per armonica. Nel caso in cui cio' che digiterete sia compreso nel nome di piu' scale, Chitabry scegliera' la prima che incontra nell'elenco.
La tonica e' una qualsiasi delle 12 note, mentre i limiti di manico vanno indicati nel formato: primotasto punto secondo tasto. Se ad esempio si desidera cercare la scala entro i primi 4 tasti del manico, scriveremo 0.4, cioe' da corda libera al quarto tasto compreso. Se, alla richiesta di inserire dei limiti di manico premiamo semplicemente invio, Chitabry assumera' 0.21 come limiti predefiniti, il che' equivale a cercare in tutta l'estensione del manico dello strumento.
Il risultato mostrato dalla funzione scale e' rappresentato dalle note trovate, incolonnate sulla sinistra della videata, ad inizio riga, seguite poi dalla o dalle posizioni in cui quella stessa nota e' presente sul manico. Nel caso in cui piu' di una posizione venga riportata per una stessa nota, sara' l'utente a decidere la piu' conveniente da includere nel proprio esercizio. Se le posizioni riportate sono troppe, si puo' chiedere a Chitabry di ripetere la ricerca della scala impostando dei limiti di manico piu' stretti.

IL PROMPT.
Il prompt e' una sequenza di lettere e parole che si trova infondo allo schermo, subito prima del cursore lampeggiante. Esso finisce con il simbolo ">" maggiore di, ed ha la funzione di riepilogare i comandi che possono essere inseriti e che quindi Chitabry si aspetta di ricevere. Infatti il prompt e' ora una sequenza di questo tipo:
(INVIO), I, NomeNota, C.T, S, M >
Come potete leggere, si tratta proprio di un riassunto di ogni comando riconosciuto dal software: invio per chiudere, NomeNota per cercare una nota, C.T e' l'abbreviazione di Corda.Tasto e serve per cercare una nota partendo da una posizione conosciuta, la S per le scale e la m per il menu'.

Ringraziamenti.
Per questo lavoro impegnativo ringrazio in ordine del tutto casuale, le seguenti persone e chiedo anticipatamente perdono se ne ho dimenticata qualcuna:
Ginevra Di Modica, Mauro Zucchi, Andrea Dessolis, Igor Zanzi.