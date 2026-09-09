"""
test_input_fisico.py
----------------------
Prova indipendente dell'hardware, prima di collegarlo alla camera vera.

Cosa fa:
  - Stampa ogni pulsante premuto e in quale "modalità demo" ti trovi.
  - Il pulsante REC cicla tra le 3 modalità demo (menu -> camera -> doom -> menu...),
    così vedi con i tuoi occhi che lo STESSO pulsante fa cose diverse a
    seconda della modalità attiva — è il cuore dell'architettura.
  - Stampa in continuo i valori raw e normalizzati della levetta, utili
    per la calibrazione di CENTRO_X/CENTRO_Y/FONDO_SCALA in input_fisico.py.

Premi Ctrl+C per uscire.
"""

import time

from input_fisico import GestoreComandi, leggi_levetta, _canale_x, _canale_y

comandi = GestoreComandi()

ORDINE_MODALITA = ["menu", "camera", "doom"]


def cambia_modalita_demo():
    i = ORDINE_MODALITA.index(comandi.modalita_corrente)
    prossima = ORDINE_MODALITA[(i + 1) % len(ORDINE_MODALITA)]
    comandi.imposta_modalita(prossima)


# --- Esempi di funzioni per ciascuna modalità -------------------------
# In modalità "menu": la croce scorre le voci, "stick" conferma.
comandi.registra("menu", "su", lambda: print("[MENU] su nel menu"))
comandi.registra("menu", "giu", lambda: print("[MENU] giù nel menu"))
comandi.registra("menu", "sinistra", lambda: print("[MENU] modalità precedente"))
comandi.registra("menu", "destra", lambda: print("[MENU] modalità successiva"))
comandi.registra("menu", "stick", lambda: print("[MENU] conferma selezione"))

# In modalità "camera": REC normalmente registra, qui lo usiamo per il demo
# di cambio modalità. Su/giù immaginiamo controllino la gamma.
comandi.registra("camera", "su", lambda: print("[CAMERA] gamma +"))
comandi.registra("camera", "giu", lambda: print("[CAMERA] gamma -"))
comandi.registra("camera", "stick", lambda: print("[CAMERA] pausa/riprendi"))

# In modalità "doom": la croce diventa movimento, stick diventa fuoco.
comandi.registra("doom", "su", lambda: print("[DOOM] avanti"))
comandi.registra("doom", "giu", lambda: print("[DOOM] indietro"))
comandi.registra("doom", "sinistra", lambda: print("[DOOM] gira a sinistra"))
comandi.registra("doom", "destra", lambda: print("[DOOM] gira a destra"))
comandi.registra("doom", "stick", lambda: print("[DOOM] fuoco!"))

# REC cambia sempre modalità in questo test, in TUTTE le modalità.
for modalita in ORDINE_MODALITA:
    comandi.registra(modalita, "rec", cambia_modalita_demo)


print("Test avviato. Premi REC per cambiare modalità demo (menu -> camera -> doom -> ...).")
print("Premi Ctrl+C per uscire.\n")

try:
    while True:
        x, y = leggi_levetta()
        print(f"\r[LEVETTA] raw=({_canale_x.value:5d},{_canale_y.value:5d})  "
              f"normalizzato=({x:+.2f},{y:+.2f})  |  modalità: {comandi.modalita_corrente}   ",
              end="", flush=True)
        time.sleep(0.2)
except KeyboardInterrupt:
    print("\nTest terminato.")
