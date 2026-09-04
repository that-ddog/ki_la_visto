"""
kinect_safe.py
----------------
Utility condivisa dagli script che mostrano un flusso Kinect (depth o
video) a schermo intero.

Il problema che risolve: le chiamate a freenect (sync_get_depth/video)
possono bloccarsi dentro il codice nativo (C) della libreria, e i normali
timeout Python (signal.alarm) non sono affidabili perché quella chiamata
può tenere il "GIL" dell'interprete, impedendo al gestore del timeout di
scattare. L'unico modo sicuro per non restare mai bloccati è far girare
quella chiamata in un PROCESSO SEPARATO: se si blocca lì, blocca solo quel
processo — la finestra e il tasto ESC nel processo principale restano
sempre reattivi, e possiamo terminare il processo bloccato dall'esterno in
qualunque momento, senza xkill o riavvii.
"""

import queue
import multiprocessing as mp


def avvia_cattura(funzione_cattura):
    """
    Avvia un processo che richiama ripetutamente funzione_cattura() (una
    funzione senza argomenti che fa l'import di freenect al suo interno e
    ritorna un frame numpy già pronto per cv2.imshow) e mette il risultato
    in una coda, tenendo solo l'ultimo frame.

    Ritorna (processo, coda). Nel ciclo principale, leggi così:
        try:
            frame = coda.get(timeout=0.05)
        except queue.Empty:
            pass  # nessun frame nuovo: va bene lo stesso, ESC resta reattivo
    """
    coda = mp.Queue(maxsize=1)

    def _loop():
        while True:
            frame = funzione_cattura()
            try:
                while True:
                    coda.get_nowait()
            except queue.Empty:
                pass
            coda.put(frame)

    processo = mp.Process(target=_loop, daemon=True)
    processo.start()
    return processo, coda


def ferma_cattura(processo):
    """Termina il processo di cattura senza pietà: se è bloccato nel driver,
    un terminate/kill lo interrompe comunque dall'esterno."""
    processo.terminate()
    processo.join(timeout=1)
    if processo.is_alive():
        processo.kill()
