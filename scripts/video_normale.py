import sys
import queue

import numpy as np
import cv2

from kinect_safe import avvia_cattura, ferma_cattura
from overlay_rec import ControlliOverlay

NOME_FINESTRA = "Normal Camera"

# NOTA: qui non tocchiamo la geometria della finestra (niente resize/move a
# schermo intero, niente fullscreen) perché su questo sistema (Qt + ambiente
# che tenta Wayland) manipolare la finestra di OpenCV può bloccare tutto il
# processo. La finestra resta quindi a dimensione di default: meno "wow",
# ma stabile. Nessuna gamma qui (è un flusso RGB, non depth), quindi la
# levetta non compare.


def cattura_un_frame():
    """Gira nel PROCESSO SEPARATO: legge un frame RGB dal Kinect e lo
    converte già in BGR per OpenCV."""
    import freenect
    video, _ = freenect.sync_get_video()
    return cv2.cvtColor(video, cv2.COLOR_RGB2BGR)


def main():
    processo, coda = avvia_cattura(cattura_un_frame)
    controlli = ControlliOverlay(con_gamma=False)

    print("Premi ESC nella finestra per uscire")
    cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(NOME_FINESTRA, controlli.on_mouse)

    ultimo_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(ultimo_frame, "In attesa del Kinect...", (60, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    try:
        while True:
            try:
                ultimo_frame = coda.get(timeout=0.05)
            except queue.Empty:
                pass

            controlli.gestisci_frame(ultimo_frame)
            cv2.imshow(NOME_FINESTRA, controlli.disegna(ultimo_frame))

            if cv2.waitKey(1) & 0xFF == 27 or controlli.richiesta_uscita:
                break
    finally:
        controlli.chiudi()
        ferma_cattura(processo)
        cv2.destroyAllWindows()

    sys.exit(0)


if __name__ == "__main__":
    main()
