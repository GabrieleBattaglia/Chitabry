# Chitabry - Studio sulla Chitarra - di Gabriele Battaglia
# Data concepimento: venerdì 7 febbraio 2020.
# 28 giugno 2024 copiato su Github

from GBUtils import dgt, manuale, menu, key
from pyo import Server, Pan, HarmTable, Osc, Adsr, Biquad
from time import sleep as aspetta
import pickle, random, sys

#COSTANTI
VERSIONE = "3.0.22 del 9 giugno 2024."
FILENOTEQRG="chitabry_notes.txt"
OTTAVA = ['DO','DO#','RE','RE#','MI','FA','FA#','SOL','SOL#','LA','LA#','SI']
SCALACROMATICA = {}
# SCALE contiene nomescala come chiave e distanza in semitoni dalla fondamentale in una lista.
SCALE = {"01 maggiore"        : [0, 2, 4, 5, 7, 9, 11, 12], \
				 "02 minore naturale" : [0, 2, 3, 5, 7, 8, 10, 12], \
				 "03 minore armonica" : [0, 2, 3, 5, 7, 8, 11, 12], \
				 "04 minore melodica" : [0, 2, 3, 5, 7, 9, 11, 12], \
				 "05 maggiore blues"  : [0, 3, 5, 6, 7, 10, 12], \
				 "06 minore blues"    : [0, 2, 3, 4, 7, 9, 12], \
				 "07 cromatica"       : [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], \
				 "08 pentatonica"     : [0, 2, 4, 7, 9, 12]}
MAINMENU = {}
MAINMENU ["---------"] = "MENU\ DI CHITABRY."
MAINMENU ["  INVIO  "] = "Esce dall'App"
MAINMENU ["  I      "] = "Mostra la guida di Chitabry"
MAINMENU ["NomeNota "] = "Trova le posizioni della nota cercata"
MAINMENU ["Cord.Tast"] = "Corda.Tasto, indica la nota in quella posizione"
MAINMENU ["  C      "] = "Accede al database degli accordi"
MAINMENU ["  S      "] = "Visualizza una scala"
MAINMENU ["  M      "] = "Visualizza questo menù"
PROMPT = "\n(INVIO), I, NomeNota, C.T, C, S, M"

serversuono=Server(verbosity=1).boot()
serversuono.start()
serversuono.amp=.45
harmonics = [1, 0.5, 0.33, 0.25, 0.2, 0.17, 0.14, 0.125, 0.11, 0.1, 0.09, 0.08, 0.07]
table = HarmTable(harmonics)
string = [Osc(table, 440, mul=.8) for i in range(6)]
stringenv = [Adsr(attack=0.01, decay=1.5, sustain=0, release=2.5, dur=4.01) for i in range(6)]
for i in range(6):
	string[i].mul = stringenv[i]
filtered_string = [Biquad(string[i], freq=800, q=1, type=2) for i in range(6)]
panned_string = [Pan(filtered_string[i], outs=2, pan=(0.3 + (i * 0.1))).out() for i in range(6)]

archivio_modificato=False; i=0
for j in range(0, 8):
	for nota in OTTAVA:
		i += 1
		SCALACROMATICA[i] = nota + str(j)
MANICO = []
for i in range(29, 75):
	MANICO.append(SCALACROMATICA[i])
CAPOTASTI = {}; i = 6
for j in [29, 34, 39, 44, 48, 53]:
	CAPOTASTI[i] = j
	i -= 1
CORDE = {}
for corda in range(6, 0, -1):
	for tasto in range(CAPOTASTI[corda], CAPOTASTI[corda]+22):
		CORDE [str(corda)+"."+str(tasto-CAPOTASTI[corda])] = SCALACROMATICA[tasto]

#QF
def Suona(t):
	'''Riceve la tablatura e permette l'ascolto delle corde'''
	print("Ascolta le corde:\nTasti da 1 a 6, (A) pennata in levare, (Q) pennata in battere\nESC per uscire.")
	it=0; frequenza=0; y=''
	for corda in range(6, 0, -1):
		j=t[it]
		if j.isdigit() and int(j)<=21:
				frequenza=note_frequenze[CORDE[f'{corda}.{j}']]
		elif j=="X": frequenza=0
		string[corda-1].freq=frequenza
		it+=1
	while True:
		scelta=key().lower()
		if scelta in '123456':
			stringenv[int(scelta)-1].stop()
			stringenv[int(scelta)-1].play()
		elif scelta==chr(27): break
		elif scelta=="a":
			for j in range(0, 6):
				stringenv[j].stop()
				stringenv[j].play()
				aspetta(.1)
		elif scelta=="q":
			for j in range(5, -1, -1):
				stringenv[j].stop()
				stringenv[j].play()
				aspetta(.1)
		else: print("Comando non valido, premi ESC")
	print("Uscita dal menù ascolto")
	return
def Barre(t):
	# riceve la tablatura e restituisce il capotasto del barrè, se lo trova
	if "0" in t: return 0
	tasti_premuti = [int(fret) for fret in t if fret not in 'X']
	if len(tasti_premuti) < 2:
		return 0
	conteggio_tasti = {}
	for tasto in tasti_premuti:
		if tasto in conteggio_tasti:
			conteggio_tasti[tasto] += 1
		else:
			conteggio_tasti[tasto] = 1
	for k,v in conteggio_tasti.items():
		if v > 0 and k <= min(list(conteggio_tasti.keys())):
			return k
	return 0

def GestoreChordpedia():
	'''Gestisce il DB degli accordi'''
	global archivio_modificato
	print("La Chordpedia. Gestore del database degli accordi.")
	mnaccordi={"a":"Aggiungi un nuovo accordo",
												"v":"Vedi accordi",
												"r":"Rimuovi un accordo",
												"i":"Torna indietro"}
	menu(d=mnaccordi,show=True)
	#QFC
	def VediTablaturaPerTasto(t):
		print("\nTablatura per tasto:")
		risultato={}
		bar=Barre(t)
		for tasto in range(0, 22):
			risultato[tasto]=""
			c=6; stopate=[]
			for j in t:
				if j != "X" and tasto==int(j):
					risultato[tasto]+=str(c)+", "
				if j=="X": stopate.append(c)
				c-=1
			if tasto>0 and tasto==int(bar): risultato[tasto]=risultato[tasto]+"Barrè!"
			if risultato[tasto][-2:]==", ": risultato[tasto]=risultato[tasto][:-2]+"."
		for k,v in risultato.items():
			if len(v)>0:
				if len(v)>2:	crd="corde"
				else: crd="corda"
				if k==0 and len(v)>=1: k1=f"Corde aperte: {v}"
				elif k==0 and len(v)<=2: k1=f"Corda aperta: {v}"
				else: k1=f"Tasto {k}, {crd}: {v}"
				print(k1)
		if len(stopate)>0:
			stp=''
			for j in stopate:
				stp+=f"{j}, "
			stp=stp[:-2]+"."
			if len(stopate)>1: k2=f"Corde stoppate: {stp}"
			else: k2=f"Corda stoppata: {stp}"
			print(k2)
		return

	def VediTablaturaPerCorda(t):
		print("\nTablatura per corda:")
		bar=Barre(t)
		if int(bar)>0: print(f"Barrè al tasto {bar}")
		it=0
		for corda in range(6, 0, -1):
			j=t[it]
			if j.isdigit() and int(j)>=1 and int(j)<=24:
				y=CORDE[f'{corda}.{j}'][:-1]
				if y[-1]=="#": y=y[:-1]+" diesis"
				print(f"Corda {corda}, tasto {j}, {y}.")
			elif j.isdigit() and int(j)==0: print(f"Corda {corda} libera, {CORDE[f'{corda}.0'][:-1]}.")
			elif j=="X": print(f"Corda {corda} stoppata.")
			it+=1
		return

	def InserisciTablatura(nuova_lista_tablature,nuovo_nome_accordo):
		while True:
				tbl=dgt(prompt=f"Tablatura: ({len(nuova_lista_tablature)+1}) - {nuovo_nome_accordo} (Tab: ", kind="s", smax=19).upper()
				if tbl=="": return ""
				stbl=tbl.split(" ")
				if len(stbl)==6: break
				print("Non sono stati inseriti sei valori, riprova.")
		return stbl
	def DaTablaturaAStringa(t):
		'''trasforma una lista di 6 valori in tablatura'''
		s=''
		for j in t:
			if j.isdigit():
				if int(j)>=0 and int(j)<=9: s+=j
				else: s+=" "+j			
			else: s+=j.upper()
		return s
	def RimuoviAccordi():
		cancello_accordo=dgt(prompt="\nInserisci l'esatto nome dell'accordo da eliminare in via definitiva: >", kind="s",smax=64).upper()
		if len(chordpedia)>0:
			if cancello_accordo in chordpedia.keys():
				del chordpedia[cancello_accordo]
				print(f"{cancello_accordo} eliminato. Ora l'archivio ne contiene {len(chordpedia)}.")
			else: print("Nome accordo non presente in Chordpedia")
		else: print("Il Database degli accordi è già vuoto.")
		return
	def VediAccordi():
		global archivio_modificato
		l=len(chordpedia)
		if l==0:
			print("\nArchivio vuoto, prima aggiungi qualche accordo.")
			return
		print(f"Visualizza uno dei {l} accordi presenti nella chordpedia.\nInizia a digitare il nome dell'accordo.")
		if l>50: l=50
		accordi_scelti_a_caso=random.sample(list(chordpedia.keys()), k=l)
		print("\nAlcuni accordi presenti nel database, scelti a caso\n")
		for j in accordi_scelti_a_caso:
			print(str(j),end=", ")
		print("\n")
		while True:
			if len(chordpedia)>1:
				trovato_accordo=''; fine_ricerca=False
				while True:
					s=key(prompt=trovato_accordo).upper()
					trovato_accordo+=s
					conta_risultati=0
					for k in chordpedia.keys():
						if trovato_accordo in k: conta_risultati+=1
					print(f"{conta_risultati} accordi trovati")
					if conta_risultati<=25:
						visualizza_risultati=1
						for k,v in chordpedia.items():
							if trovato_accordo in k: print(f"{visualizza_risultati}. {k};") # aggiungi visualizzazione tablature qui
							visualizza_risultati+=1
					if ord(s)==13 and trovato_accordo[:-1] in chordpedia.keys():
						for k in chordpedia.keys():
							if trovato_accordo[:-1] == k:
								trovato_accordo=k
								fine_ricerca=True
								continue
					elif trovato_accordo not in chordpedia.keys() and conta_risultati==0:
						print("Accordo non trovato. Ricomincia a digitare")
						trovato_accordo=''
					elif conta_risultati==1:
						for k in chordpedia.keys():
							if trovato_accordo in k:
								trovato_accordo=k
								fine_ricerca=True
								continue
					if fine_ricerca: break
			else: trovato_accordo=list(chordpedia.keys())[0]
			if len(chordpedia[trovato_accordo])>1:
				print(f"L'accordo {trovato_accordo} ha {len(chordpedia[trovato_accordo])} tablature registrate. Scegline una:")
				dz_tablature_presenti_in_accordo={}; indice_tablature_in_accordo=1
				for j in chordpedia[trovato_accordo]:
					dz_tablature_presenti_in_accordo[indice_tablature_in_accordo]=DaTablaturaAStringa(chordpedia[trovato_accordo][indice_tablature_in_accordo-1])
					indice_tablature_in_accordo+=1
				menu(d=dz_tablature_presenti_in_accordo,show=True)
				tablatura_scelta=menu(d=dz_tablature_presenti_in_accordo,keyslist=True)
			else: tablatura_scelta=1
			print(f"\nAccordo {trovato_accordo}, tablatura {tablatura_scelta} Tab: {DaTablaturaAStringa(chordpedia[trovato_accordo][int(tablatura_scelta)-1])}")
			mn_gestione_tablatura={"c":"Visualizza in ordine di corda",
																										"t":"Visualizza in ordine di tasto",
																										"a":"Ascolta le note",
																										"m":"Modifica tablatura",
																										"r":"Rimuovi questa tablatura",
																										"i":"Esci e torna indietro al menù principale",
																										"p":"Prosegui nella consultazione",}
			menu(d=mn_gestione_tablatura,show=True)
			while True:
				s=menu(d=mn_gestione_tablatura,ntf="Comando non valido",keyslist=True)
				if s=="i": return
				elif s=="p":
					print("\nProsegui con la consultazione degli accordi")
					return
				elif s=="c": VediTablaturaPerCorda(chordpedia[trovato_accordo][int(tablatura_scelta)-1])
				elif s=="t": VediTablaturaPerTasto(chordpedia[trovato_accordo][int(tablatura_scelta)-1])
				elif s=="a": Suona(chordpedia[trovato_accordo][int(tablatura_scelta)-1])
				elif s=="r":
					if len(chordpedia[trovato_accordo])==1:
						print("\nNon puoi rimuovere l'ultima tablatura di questo accordo.\nRimuovi invece l'intero accordo dal menù precedente.")
					else:
						del chordpedia[trovato_accordo][int(tablatura_scelta)-1]
						print(f"Rimozione effettuata. Ora {trovato_accordo} contiene {len(chordpedia[trovato_accordo])} tablature.\nRitorno al menù precedente.")
						archivio_modificato=True
						return
				elif s=="m":
					print(f"\nTab: ({tablatura_scelta}) = {DaTablaturaAStringa(chordpedia[trovato_accordo][int(tablatura_scelta)-1])}. Nuova tab? ")
					stbl=InserisciTablatura([],trovato_accordo)
					chordpedia[trovato_accordo][int(tablatura_scelta)-1]=stbl
					archivio_modificato=True
					print("Tablatura modificata")
					return
				#qui
		return

	def Aggiungiaccordo():
		print("Aggiungi un nuovo accordo alla collezione")
		while True:
			nuovo_nome_accordo=dgt(prompt="Nome accordo: ",kind="s",smin=1,smax=40).upper()
			if nuovo_nome_accordo not in chordpedia.keys(): break
			print("Già presente della collezione. Ripova con un nome diverso.")
		nuova_lista_tablature=[]
		print("Inserisci la tablatura: numeri separati da spazi indicando il tasto da premere\ndalla corda 6 alla corda 1. 0 indica corda aperta, X corda muta\nConcludi con un INVIO a vuoto.")
		while True:
			stbl=InserisciTablatura(nuova_lista_tablature,nuovo_nome_accordo)
			if stbl=="": break
			nuova_lista_tablature.append(stbl)
		return nuovo_nome_accordo, nuova_lista_tablature
	while True:
		s=menu(d=mnaccordi, ntf="Non trovato", keyslist=True)
		if s=="i": break
		elif s=="a":
			nuovo_accordo,nuova_lista_tablature=Aggiungiaccordo()
			chordpedia[nuovo_accordo]=nuova_lista_tablature
			archivio_modificato=True
			print(f"La Chordpedia ora contiene {len(chordpedia)} accordi.")
		elif s=="v":
			VediAccordi()
		elif s=="r":
			RimuoviAccordi()
			archivio_modificato=True
	return

def Manlimiti(s):
	''' riceve una stringa contenente 2 numeri separati da un punto, 6.3
	restituisce 2 interi.
	se non è possibile stampa un errore e restituisce 0 e 21'''
	if "." not in s:
		print("Errore: la stringa immessa non contiene un punto.")
		return 0, 21
	if " " in s:
		print("Errore: sono stati inseriti spazi.")
		return 0, 21
	s2 = s.split(".")
	maninf, mansup = s2[0], s2[1]
	if not maninf.isdigit() or not mansup.isdigit():
		print("Errore: sono stati inseriti valori non numerici.")
		return 0, 21
	return int(maninf), int(mansup)
def VMenu(mm):
	'''Riceve e Mostra il menù'''
	for k, v in mm.items():
		print(f"---({k}) - - {v}.")
	return

def MostraCorde(n, x = True, rp = False):
	'''Questa routine mostra tutte le corde e le posizioni della nota cercata, sul manico
	riceve la nota;
	x, se vera, indica che la nota cercata contiene l'ottava;
	rp se vero restituisce il risultato invece di stamparlo,   se rp è falso, non restituisce nulla'''
	n = n.upper()
	if not rp: print(f"Nota {n} trovata nelle seguenti posizioni sul manico:")
	posizioni = []
	for k, v in CORDE.items():
		ks = k.split("."); ks1 = int(ks[1])
		if x and n == v:
			posizioni.append(k)
		elif not x and n in v:
			posizioni.append(k)
	if not rp:
		Spacchetta(posizioni)
		print()
		return
	else:
		return(posizioni)

def Spacchetta(k):
	'''Funzione di servizio di MostraCorde.
	riceve elenco posizioni e stampa suddividendo le corde.
	non ritorna nulla'''
	cc = 0
	for pos in k:
		pc, pt = pos.split(".")[0], pos.split(".")[1]
		if cc != pc: print(f"\nCorda {pc}, tasti: ",end="")
		cc = pc
		if cc == pc:
			print(pt, end=" ")
		else: cc = pc
	return

def MostraScale():
	'''Visualizza le scale'''
	print("Visualizzatore scale.\nPuoi scegliere fra i seguenti modelli:")
	for k in SCALE:
		print("- - - " + k.title())
	continua = True
	while continua:
		s = dgt("Scrivi il nome o parte del nome della scala che desideri: ", smin=2, smax=15)
		for k in SCALE:
			if s in k:
				continua=False
				scalaselezionata = k.title()
				print(scalaselezionata)
		if continua:
			print(f"{s} non è contenuto da nessuno dei nomi di scala che Chitabry conosce.")
	print("Ora è necessario scegliere la nota tonica della scala.")
	while True:
		print("Seleziona una di queste:\n\t" + str(OTTAVA), end=": ")
		s = dgt(smin=2, smax=3).upper()
		if s.upper() in OTTAVA: break
	notatonica = s
	print(f"Ottimo, selezionata la nota, {s}.")
	print(f"Ricerca della scala {scalaselezionata} di {notatonica},")
	for indiceprimanota in range(0, 12):
		if notatonica.upper() in MANICO[indiceprimanota]: break
	scasup = []; scainf = []; interv = 0; indm = indiceprimanota; inds = 0; indls = len(SCALE[scalaselezionata.lower()])
	while True:
		if indm + interv <= 44:
			interv = SCALE[scalaselezionata.lower()][inds % indls]
			if interv != 12: scasup.append(MANICO[indm + interv])
			inds += 1
			if interv == 12: indm += 12
		else: break
	inds = -2
	while True:
		interv = 12 - SCALE[scalaselezionata.lower()][inds]
		if indiceprimanota - interv >= 0:
			scainf.append(MANICO[indiceprimanota- interv])
			inds -= 1
		else: break
	scainf.reverse()
	ris = scainf + scasup
	print("Ora se desideri, puoi indicare una porzione di manico entro cui cercare.\nIndica 2 numeri separati da un punto che specificano i tasti entro cui effettuare la ricerca.\n\tAd esempio 0.4 indica da corda vuota al 4° tasto, compreso.\nBatti invio a vuoto per cercare le note in tutto il manico della chitarra.")
	scelta = dgt("Limite inferiore.Limite superiore: #.# >")
	if scelta == "": maninf = 0; mansup = 21
	else: maninf, mansup = Manlimiti(scelta)
	print(f"Nome della nota,   Limiti del manico dal tasto {maninf} al tasto {mansup} ...")
	for j in ris:
		l = MostraCorde(j, True, True)  
		print(j, end=": ")
		for l1 in l:
			l2 = int(l1.split(".")[1])
			if l2 >= maninf and l2 <= mansup: print(l1, end=", ")
		print()
	print("Riepilogo scala da tonica a tonica:\n\t", end="")
	salta = False
	for j in scasup:
		print(j[:-1], end=" ")
		if salta and j[:-1] == notatonica: break
		if not salta: salta = True
	print()
	return
#Main
print(f"\nBenvenuto in Chitabry, l'App per familiarizzare con la Chitarra.\n\tVersione: {VERSIONE} di Gabriele Battaglia.")
print("\n---- Digita M, per visualizzare il menù dell'App.")

try:
	f=open("chitabry.cho", "rb")
	chordpedia=pickle.load(f)
	f.close()
	tablature=0
	archivio_modificato=False
	for k,v in chordpedia.items():
		tablature+=len(chordpedia[k])
	print(f"DB caricato. Contiene {len(chordpedia)} accordi ed un totale di {tablature} tablature.")
except IOError:
	print("Database degli accordi non trovato: ne creo uno nuovo.")
	chordpedia={}
	archivio_modificato=True
try:
	note_frequenze={}
	with open(FILENOTEQRG, "r") as file:
		for line in file:
			note, frequency = line.strip().split()
			note_frequenze[note] = float(frequency)
	print("Registro note caricato con successo.")
except IOError:
	print(f"Il file {FILENOTEQRG} non è stato trovato.\nFarne richiesta all'autore del programma.")
	sys.exit()

while True:
	s = dgt(PROMPT+" > ")
	if s == "": break
	elif s == "m":
		VMenu(MAINMENU)
	elif s == "c": GestoreChordpedia()
	elif s == "i":
		manuale("ChitabryMan.txt")
	elif s == "s":
		MostraScale()
	elif s.upper() in CORDE.values():
		MostraCorde(s)
	elif s.upper() in OTTAVA:
		MostraCorde(s, False)
	elif s[0] in '123456':
		if s[1] == ".":
			if s.split('.')[1].isdigit() and int(s.split('.')[1]) >= 0 and int(s.split('.')[1]) < 22:
				print(f"Sulla corda {s[0]}, tasto {s.split('.')[1]}, si trova la nota: {CORDE[s]}")
				string[int(s[0])-1].freq=note_frequenze[CORDE[s]]
				stringenv[int(s[0])-1].play()
		s=''
	else: print(f"{s} comando non riconosciuto.\n\tDigita M seguito da invio per il menù.")
if archivio_modificato:
	f=open("chitabry.cho", "wb")
	pickle.dump(chordpedia,f, protocol=pickle.HIGHEST_PROTOCOL)
	f.close()
	print("Chordpedia salvata nel file: chitabry.cho.")
else: print("Salvataggio della chordpedia non necessario")
print(f"Arrivederci da Chitabry versione: {VERSIONE}")
serversuono.stop()
aspetta(0.4)
serversuono.shutdown()
aspetta(0.4)
sys.exit()