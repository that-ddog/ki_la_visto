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
    DOOM                           -> combo di tutti i pulsanti insieme
    MUOVI su|giu|sinistra|destra   -> la levetta ha superato la soglia in quella direzione
    ERRORE <messaggio>             -> hardware non disponibile
"""

import time

import input_fisico

SOGLIA_LEVETTA = 0.5
COOLDOWN_MOVIMENTO_S = 0.35
INTERVALLO_CICLO_S = 0.05


def emetti(testo):
    print(testo, flush=True)


def main():
    try:
        comandi = input_fisico.inizializza()
    except Exception as e:
        emetti(f"ERRORE {e}")
        return

    comandi.imposta_modalita("menu")
    comandi.registra("menu", "giu", lambda: emetti("SELEZIONA"))
    comandi.registra_combo_tutti("menu", lambda: emetti("DOOM"))

    ultimo_movimento = 0.0
    try:
        while True:
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
    except KeyboardInterrupt:
        pass
    finally:
        input_fisico.termina()


if __name__ == "__main__":
    main()
