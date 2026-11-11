#!/usr/bin/env python3
"""
menu_input_bridge.py
----------------------
Piccolo processo "usa e getta": legge pulsanti fisici e levetta per la
modalità MENU, e comunica gli eventi alla GUI tramite stdout (una riga di
testo per evento). Viene lanciato di nuovo da zero ogni volta che la GUI
torna visibile, e chiuso (terminato) subito prima di aprire una camera.

Perché un processo a parte invece di gestire i pulsanti direttamente nella
GUI: gpiozero/lgpio, inizializzati e chiusi più volte DENTRO LO STESSO
processo Python, prima o poi vanno in una race condition interna (un
thread di sottofondo va in errore) che rende un pulsante "sordo". Un
processo fresco ogni volta invece funziona sempre in modo affidabile — lo
confermano tutti gli script delle camere, che non hanno mai avuto questo
problema perché ognuno inizializza l'hardware una volta sola nella vita.

Righe stampate su stdout (una per evento, con flush immediato):
    SELEZIONA                     -> il pulsante "giù" è stato premuto
    DOOM                           -> (per ora non emessa: combo troppo scomoda con 7 pulsanti)
    MUOVI su|giu|sinistra|destra   -> la levetta ha superato la soglia in quella direzione
    ERRORE <messaggio>             -> hardware non disponibile
"""

import ctypes
import os
import signal
import time

import input_fisico

SOGLIA_LEVETTA = 0.5
COOLDOWN_MOVIMENTO_S = 0.35
INTERVALLO_CICLO_S = 0.05


# Se la GUI che ci ha lanciato muore (chiusura forzata, xkill...), questo
# processo NON deve restare vivo da solo: terrebbe occupati i GPIO per
# sempre ("GPIO busy") e i pulsanti non andrebbero più in nessuna app.
# Tre protezioni, dalla più immediata alla più "a prova di bomba":
#   1. il kernel ci manda SIGTERM appena muore il processo genitore
#   2. se la GUI non legge più (pipe rotta), usciamo
#   3. a ogni giro controlliamo che il genitore sia ancora lo stesso
_GENITORE = os.getppid()
_stato = {"esci": False}


def _su_sigterm(signum, frame):
    raise SystemExit(0)


def _muori_col_genitore():
    try:
        PR_SET_PDEATHSIG = 1
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
    except Exception:
        pass  # la protezione 3 copre comunque


def emetti(testo):
    try:
        print(testo, flush=True)
    except (BrokenPipeError, OSError):
        # La GUI non c'è più: chiudiamo (anche se siamo nel thread di gpiozero).
        _stato["esci"] = True


def main():
    signal.signal(signal.SIGTERM, _su_sigterm)
    _muori_col_genitore()
    if os.getppid() != _GENITORE:
        return  # la GUI è morta prima ancora che partissimo

    try:
        comandi = input_fisico.inizializza()
    except Exception as e:
        emetti(f"ERRORE {e}")
        return

    comandi.imposta_modalita("menu")
    comandi.registra("menu", "giu", lambda: emetti("SELEZIONA"))
    # Combo "tutti insieme" per Doom RIMOSSA: con 7 pulsanti è troppo scomodo
    # da premere in contemporanea. Il meccanismo resta disponibile in
    # GestoreComandi (registra_combo_tutti) se in futuro torna utile con
    # meno pulsanti richiesti o un'altra idea.

    ultimo_movimento = 0.0
    try:
        while not _stato["esci"]:
            if os.getppid() != _GENITORE:
                break  # GUI morta: liberiamo i GPIO
            x, y = input_fisico.leggi_levetta()
            ora = time.time()
            if ora - ultimo_movimento > COOLDOWN_MOVIMENTO_S:
                direzione = None
                if x > SOGLIA_LEVETTA:
                    direzione = "destra"
                elif x < -SOGLIA_LEVETTA:
                    direzione = "sinistra"
                elif y > SOGLIA_LEVETTA:
                    direzione = "su"
                elif y < -SOGLIA_LEVETTA:
                    direzione = "giu"
                if direzione:
                    emetti(f"MUOVI {direzione}")
                    ultimo_movimento = ora
            time.sleep(INTERVALLO_CICLO_S)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        input_fisico.termina()


if __name__ == "__main__":
    main()
