#!/usr/bin/env python3
"""
doom_ponte.py
---------------
Processo "ponte" per la modalità DOOM. È quello che la GUI lancia quando
premi "D": fa da tramite fra i pulsanti fisici e Chocolate Doom.

Cosa fa, in ordine:
  1. sistema i tasti nella configurazione di Chocolate Doom (configura_doom.py)
  2. crea tastiera + mouse virtuali (controlli_doom.py)
  3. prende GPIO e I2C (input_fisico.inizializza) e attiva il profilo "doom"
  4. avvia chocolate-doom e, finché è aperto, legge la levetta e la
     trasforma in frecce
  5. quando esci da Doom: rilascia tutti i tasti, chiude le periferiche
     virtuali e libera GPIO/I2C, poi termina -> la GUI torna visibile e
     riprende i pulsanti per il menu (stesso schema delle camere).

Se qualcosa non va (manca evdev, niente permessi su /dev/uinput, hardware
scollegato) Doom parte lo stesso, giocabile da tastiera vera: il motivo
viene stampato nel terminale.

Uso:
    python3 doom_ponte.py               -> avvia Doom con i comandi fisici
    python3 doom_ponte.py --solo-input  -> NON avvia Doom: crea solo la
        tastiera/mouse virtuali e stampa gli eventi. Utile per provare i
        pulsanti aprendo un editor di testo: premendo il bianco deve
        comparire "," , il nero ".", la levetta premuta "y", ecc.
        Ctrl+C per uscire.

Preparazione UNA TANTUM sul Raspberry (vedi anche il messaggio in chat):
    ~/kinect-py311/bin/pip install evdev
    echo 'KERNEL=="uinput", GROUP="input", MODE="0660"' | sudo tee /etc/udev/rules.d/99-uinput.rules
    echo uinput | sudo tee /etc/modules-load.d/uinput.conf
    sudo usermod -aG input $USER
    (poi riavvia il Raspberry)
"""

import shutil
import signal
import subprocess
import sys
import time

import input_fisico
import configura_doom

COMANDO_DOOM = [shutil.which("chocolate-doom") or "/usr/games/chocolate-doom"]

INTERVALLO_CICLO_S = 0.01      # lettura levetta (l'ADC di fatto limita a ~40 letture/s)
ATTESA_DISPOSITIVI_S = 0.6     # tempo perché il sistema "veda" le periferiche virtuali


def _su_sigterm(signum, frame):
    # La GUI chiude questo processo con terminate() (es. chiusura app):
    # trasformiamo il segnale in un'uscita normale, così il blocco finally
    # rilascia tasti, periferiche e GPIO.
    raise SystemExit(0)


def main():
    solo_input = "--solo-input" in sys.argv
    signal.signal(signal.SIGTERM, _su_sigterm)

    if not solo_input:
        configura_doom.applica_configurazione()

    dispositivi = None
    controlli = None
    comandi = None
    doom = None

    try:
        try:
            from controlli_doom import ControlliDoom, DispositiviVirtuali
            dispositivi = DispositiviVirtuali()
            controlli = ControlliDoom(dispositivi)
        except Exception as ex:
            print(f"[DOOM] Tastiera/mouse virtuali NON disponibili ({ex}).")
            print("[DOOM] Doom partirà senza comandi fisici. Controlla evdev e i permessi su /dev/uinput.")

        if controlli is not None:
            try:
                comandi = input_fisico.inizializza()
                input_fisico.collega_controlli_doom(comandi, controlli)
            except Exception as ex:
                print(f"[DOOM] Pulsanti/levetta non disponibili ({ex}): niente comandi fisici.")
                comandi = None

        if dispositivi is not None:
            time.sleep(ATTESA_DISPOSITIVI_S)

        if solo_input:
            print("[DOOM] Modalità --solo-input: premi i pulsanti, Ctrl+C per uscire.")
        else:
            print(f"[DOOM] Avvio: {' '.join(COMANDO_DOOM)}")
            doom = subprocess.Popen(COMANDO_DOOM)

        levetta_attiva = controlli is not None and comandi is not None
        while True:
            if doom is not None and doom.poll() is not None:
                print("[DOOM] Doom chiuso.")
                break
            if levetta_attiva:
                try:
                    x, y = input_fisico.leggi_levetta()
                    controlli.aggiorna_levetta(x, y)
                except Exception as ex:
                    # Una lettura I2C andata male non deve far cadere il ponte.
                    print(f"[DOOM] Lettura levetta fallita: {ex}")
                    time.sleep(0.2)
            time.sleep(INTERVALLO_CICLO_S)

    except KeyboardInterrupt:
        pass
    finally:
        if doom is not None and doom.poll() is None:
            doom.terminate()
            try:
                doom.wait(timeout=3)
            except subprocess.TimeoutExpired:
                doom.kill()
        # Prima stacchiamo i pulsanti (così non arrivano altre pressioni),
        # poi rilasciamo i tasti rimasti giù, infine chiudiamo le periferiche.
        if comandi is not None:
            input_fisico.termina()
        if controlli is not None:
            controlli.rilascia_tutto()
        if dispositivi is not None:
            dispositivi.chiudi()
        print("[DOOM] Ponte chiuso, hardware liberato.")


if __name__ == "__main__":
    main()
