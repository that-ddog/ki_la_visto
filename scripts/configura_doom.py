#!/usr/bin/env python3
"""
configura_doom.py
-------------------
Imposta nei file di configurazione di Chocolate Doom i tasti che il
profilo Doom (controlli_doom.py) si aspetta. Viene chiamato in automatico
da doom_ponte.py a ogni avvio di Doom, così anche se cambi qualcosa da
chocolate-doom-setup i nostri tasti tornano sempre a posto. Puoi anche
lanciarlo a mano:  python3 configura_doom.py

File toccati (li crea se non esistono ancora; Doom li completerà da solo
con tutte le altre opzioni alla prima chiusura):
    ~/.local/share/chocolate-doom/default.cfg         (tasti "classici")
    ~/.local/share/chocolate-doom/chocolate-doom.cfg  (tasti extra, es. arma successiva)

ATTENZIONE: nei file .cfg di Chocolate Doom i tasti NON sono scritti come
lettere ma come "scancode" della vecchia tastiera DOS. Tabella di quelli usati:
    1 = Esc   21 = Y   27 = ]   51 = ,   52 = .   54 = Shift   57 = Spazio
    72 = freccia su   75 = freccia sinistra   77 = freccia destra   80 = freccia giù
"""

import os
import re

CARTELLA_CONFIG = os.path.expanduser("~/.local/share/chocolate-doom")

IMPOSTAZIONI = {
    "default.cfg": {
        "use_mouse": 1,
        "mouseb_fire": 0,         # click sinistro = spara (il rosso)
        "key_up": 72,             # levetta su = avanti
        "key_down": 80,           # levetta giù = indietro
        "key_left": 75,           # levetta sx = gira a sinistra
        "key_right": 77,          # levetta dx = gira a destra
        "key_strafeleft": 51,     # bianco = ,
        "key_straferight": 52,    # nero = .
        "key_speed": 54,          # LB = Shift (corsa)
        "key_use": 57,            # verde = Spazio
    },
    "chocolate-doom.cfg": {
        "key_nextweapon": 27,     # giallo = ] = arma successiva
        "key_menu_activate": 1,   # bianco+giallo = Esc
        "key_menu_confirm": 21,   # pressione levetta = Y
    },
}


def _aggiorna_file(percorso, valori):
    righe = []
    if os.path.isfile(percorso):
        with open(percorso, "r", encoding="utf-8", errors="replace") as f:
            righe = f.read().splitlines()

    mancanti = dict(valori)
    cambiato = False
    for i, riga in enumerate(righe):
        m = re.match(r"^(\S+)(\s+)(.*)$", riga)
        if not m or m.group(1) not in mancanti:
            continue
        nome = m.group(1)
        nuovo = str(mancanti.pop(nome))
        if m.group(3).strip() != nuovo:
            righe[i] = f"{nome}{m.group(2)}{nuovo}"
            cambiato = True

    for nome, valore in mancanti.items():
        righe.append(f"{nome:<30}{valore}")
        cambiato = True

    if cambiato:
        if os.path.isfile(percorso) and not os.path.isfile(percorso + ".originale"):
            # Copia di sicurezza della configurazione com'era prima del nostro primo intervento.
            with open(percorso, "r", encoding="utf-8", errors="replace") as src, \
                 open(percorso + ".originale", "w", encoding="utf-8") as dst:
                dst.write(src.read())
        with open(percorso, "w", encoding="utf-8") as f:
            f.write("\n".join(righe) + "\n")
    return cambiato


def applica_configurazione():
    """Ritorna True se tutto è andato bene (anche se non c'era nulla da cambiare)."""
    try:
        os.makedirs(CARTELLA_CONFIG, exist_ok=True)
        for nome_file, valori in IMPOSTAZIONI.items():
            percorso = os.path.join(CARTELLA_CONFIG, nome_file)
            if _aggiorna_file(percorso, valori):
                print(f"[DOOM-CFG] Aggiornato {percorso}")
        return True
    except Exception as ex:
        print(f"[DOOM-CFG] Configurazione non applicata: {ex}")
        return False


if __name__ == "__main__":
    applica_configurazione()
    print("Fatto.")
