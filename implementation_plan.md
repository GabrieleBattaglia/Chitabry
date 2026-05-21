# Piano di Implementazione: Risoluzione "Troppe Dita" (Issue #31)

Questo piano descrive le modifiche da apportare per risolvere il problema dell'assegnazione verbale di dita fittizie (es. "Dito 5" o superiore) nella descrizione degli accordi generati, allineando l'algoritmo di visualizzazione con i vincoli fisici e la logica del solutore CSP.

## User Review Required

> [!IMPORTANT]
> L'intervento corregge una discrepanza tra il solutore CSP (che impone al massimo 4 dita fisiche) e il modulo di formattazione verbale. Non ci sono impatti sulla logica di generazione degli accordi validi, ma solo sulla precisione della descrizione testuale.

## Open Questions

Nessuna.

## Proposed Changes

### Costruttore Accordi

#### [MODIFY] [generatore_accordi.py](file:///E:/git/Mine/Chitabry/generatore_accordi.py)
*   **Modifica di `analizza_difficolta_e_diteggiatura`**:
    Riscrivere la sezione di assegnazione delle dita per il caso con più di 4 tasti premuti (`len(tasti_premuti_idx) > 4`) utilizzando l'algoritmo di scansione a blocchi contigui senza ostacoli di `max_fingers_constraint`.
    Assegnare tutte le note al tasto minimo al Dito 1 (attivando il barré se necessario).
    Assegnare le note superiori (tasto > min_tasto) alle dita successive (2, 3, 4) raggruppandole in mini-barré se contigue e non separate da note a tasti differenti su corde intermedie.

### Versione di Chitabry

#### [MODIFY] [Chitabry.py](file:///E:/git/Mine/Chitabry/Chitabry.py)
*   Aggiornare la costante `VERSIONE` alla versione `6.8.4 del 21 maggio 2026.` e inserire un commento descrittivo nei commenti iniziali per documentare le modifiche alla diteggiatura.

## Verification Plan

### Automated Tests
- Non applicabili.

### Manual Verification
- **Verifica accordi complessi**: Generare accordi che utilizzano mini-barré interni (es. barré al tasto 3 e mini-barré al tasto 5 su corde centrali). Verificare che la descrizione visualizzata utilizzi correttamente dita comprese tra 1 e 4 e che mostri correttamente l'etichetta "Piccolo barré".
