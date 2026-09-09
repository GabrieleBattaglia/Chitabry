# Chitabry, ricerca: la scelta di una voce per testo parziale, condivisa da scale e accordi.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.

from GBUtils import dgt


def fuzzy_search_and_select(search_dict: dict, search_prompt: str, item_type: str = "elemento") -> str | None:
    """Cerca un testo parziale, senza distinguere le maiuscole, nei valori di
    un dizionario chiave-nome, elenca i risultati numerati e chiede quale
    scegliere. Restituisce la chiave scelta, o None se l'utente annulla."""
    while True:
        search_term = dgt(search_prompt, kind="s").strip().lower()
        if not search_term:
            print("Ricerca annullata.")
            return None
        # Le voci di servizio non partecipano alla ricerca
        matches = {
            chiave: nome
            for chiave, nome in search_dict.items()
            if chiave not in ("...", "manuale") and search_term in nome.lower()
        }
        num_matches = len(matches)
        if num_matches == 0:
            print(f"Nessun {item_type} trovato contenente '{search_term}'. Riprova o premi Invio per annullare.")
            continue
        if num_matches > 20:
            print(f"Trovati troppi risultati ({num_matches}, il massimo e' 20). Affina la ricerca o premi Invio per annullare.")
            continue
        print(f"Risultati trovati per '{search_term}':")
        match_list = list(matches.items())
        for i, (_chiave, nome) in enumerate(match_list):
            print(f" {i + 1}: {nome}")
        while True:
            choice_str = dgt(f"Scegli il numero (1-{num_matches}) o Invio per annullare: ", kind="s").strip()
            if not choice_str:
                print("Selezione annullata.")
                return None
            try:
                choice_idx = int(choice_str) - 1
            except ValueError:
                print("Inserisci un numero.")
                continue
            if 0 <= choice_idx < num_matches:
                chiave, nome = match_list[choice_idx]
                print(f"Selezionato: {nome}")
                return chiave
            print("Numero non valido.")
