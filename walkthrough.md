# Walkthrough: Modifiche Recenti Chitabry
 
Questo documento riassume le modifiche apportate per l'implementazione del Pathfinder flessibile per la generazione delle diteggiature delle scale e per la risoluzione dell'impostazione "Troppe Dita" negli accordi.
 
## Modifiche Apportate
 
### Versionamento
- Aggiornata la versione di [Chitabry.py](file:///E:/git/Mine/Chitabry/Chitabry.py) alla `v6.8.4` del `21 maggio 2026`.
 
### Costruttore Accordi (generatore_accordi.py) - Risoluzione "Troppe Dita" (Issue #31)
- **Modifica di `analizza_difficolta_e_diteggiatura`**: Riscritto il calcolo per gli accordi con più di 4 tasti premuti. Ora le note al tasto minimo sono affidate al Dito 1 (attivando il barré principale), mentre le note successive sono assegnate in modo ottimizzato alle dita 2, 3 e 4, raggruppando eventuali mini-barré interni sulle corde adiacenti senza ostacoli intermedi. Questo allinea la formattazione verbale con i vincoli CSP di `max_fingers_constraint`, eliminando dita fittizie come "Dito 5" o superiore.

### Pathfinder Scale (generatore_scale.py)
- **Modifica Ricerca DFS**: Rimosso il vincolo fisso `cand['string'] >= last_pos['string']` all'interno della funzione di backtracking `dfs` in [generatore_scale.py](file:///E:/git/Mine/Chitabry/generatore_scale.py). Questo permette di generare percorsi in cui la corda successiva è più grave di quella precedente o non adiacente.
- **Scoring dei passaggi di corda**: Aggiunta la logica di valutazione dinamica dei passaggi di corda all'interno della funzione `_score_and_finger_path`:
  - Per ogni arretramento di corda (passaggio a corda più grave per suonare una nota più acuta), lo score viene penalizzato di `150` punti per ogni corda di distanza.
  - Per ogni salto di corda (passaggio non adiacente, distanza > 1), lo score viene penalizzato di `100` punti per ogni corda saltata oltre alla prima.

---

## Piano di Verifica Consigliato

### Verifica del Pathfinder con Forme Standard e Diagonali
1. Avviare Chitabry eseguendo `python Chitabry.py`.
2. Scegliere la sezione "Scale" (scelta 6).
3. Selezionare una tonica (es. DO) e una scala diagonale o a più ottave (es. una scala maggiore o minore a 2 ottave).
4. Scegliere un box di tasti ristretto ma sufficiente (es. tasti 5-8 o 5-9).
5. Verificare che vengano proposte fino a 5 diteggiature e che:
   - Le forme lineari (CAGED standard) mantengano i punteggi di difficoltà più bassi (quindi più comode).
   - Eventuali percorsi che richiedono di saltare corde o arretrare vengano visualizzati in fondo alla lista con una percentuale di difficoltà più alta, ma che non causino più la dicitura "Nessuna diteggiatura fisicamente possibile trovata".
