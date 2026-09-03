import sys
import queue
import multiprocessing as mp

import numpy as np
import cv2

NOME_FINESTRA = "Normal Camera"


def _processo_cattura(coda):
    """
    Gira in un PROCESSO SEPARATO (non solo un thread): prende i frame dal
    Kinect e li mette in coda. Isolandolo così, se la chiamata a freenect si
    blocca dentro il codice nativo, blocca solo questo processo — la
    finestra e i tasti nel processo principale restano sempre reattivi,
    perché non stanno più aspettando direttamente il Kinect.
    """
    import freenect  # import qui dentro: ogni processo ha il suo contesto
    while True:
        video, _ = freenect.sync_get_video()
        # teniamo in coda solo l'ultimo frame: se il processo principale è
        # più lento, scartiamo i frame vecchi invece di accumularli
        try:
            while True:
                coda.get_nowait()
        except queue.Empty:
            pass
        coda.put(video)


def main():
    coda = mp.Queue(maxsize=1)
    processo = mp.Process(target=_processo_cattura, args=(coda,), daemon=True)
    processo.start()

    print("Premi ESC nella finestra per uscire")
    cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)

    ultimo_frame = None
    schermata_attesa = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(schermata_attesa, "In attesa del Kinect...", (60, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    try:
        while True:
            # Aspettiamo un frame per massimo 0.05s: se non arriva, non è
            # un problema, il ciclo continua comunque e ESC resta reattivo.
            try:
                video = coda.get(timeout=0.05)
                ultimo_frame = cv2.cvtColor(video, cv2.COLOR_RGB2BGR)
            except queue.Empty:
                pass

            cv2.imshow(NOME_FINESTRA, ultimo_frame if ultimo_frame is not None else schermata_attesa)

            if cv2.waitKey(1) & 0xFF == 27:
                break
    finally:
        # Chiudiamo il processo di cattura senza pietà: se è bloccato nel
        # driver, un terminate/kill lo interrompe comunque dall'esterno.
        processo.terminate()
        processo.join(timeout=1)
        if processo.is_alive():
            processo.kill()
        cv2.destroyAllWindows()

    sys.exit(0)


if __name__ == "__main__":
    main()
