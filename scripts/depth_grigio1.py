import sys
import queue

import numpy as np
import cv2

from kinect_safe import avvia_cattura, ferma_cattura
from overlay_rec import ControlliOverlay

NOME_FINESTRA = "Depth Camera 1"

# Versione "semplice": normalizza ogni frame sul proprio valore massimo,
# senza calibrazione in mm né filtro anti-rumore. Nessuna gamma da
# regolare, quindi qui la levetta non compare (con_gamma=False sotto).


def cattura_un_frame():
    """Gira nel PROCESSO SEPARATO: legge un frame dal Kinect e lo converte
    già in grigio, così il processo principale deve solo mostrarlo."""
    import freenect
    depth, _ = freenect.sync_get_depth()
    depth = depth.astype(np.float32)
    depth = (depth / depth.max()) * 255
    return depth.astype(np.uint8)


def main():
    processo, coda = avvia_cattura(cattura_un_frame)
    controlli = ControlliOverlay(con_gamma=False)

    print("Premi ESC nella finestra per uscire")
    cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(NOME_FINESTRA, controlli.on_mouse)

    ultimo_frame_grigio = np.zeros((480, 640), dtype=np.uint8)
    cv2.putText(ultimo_frame_grigio, "In attesa del Kinect...", (60, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2)

    try:
        while True:
            try:
                ultimo_frame_grigio = coda.get(timeout=0.05)
            except queue.Empty:
                pass  # nessun frame nuovo: va bene lo stesso, ESC/click restano reattivi

            frame_pulito = cv2.cvtColor(ultimo_frame_grigio, cv2.COLOR_GRAY2BGR)
            controlli.gestisci_frame(frame_pulito)
            cv2.imshow(NOME_FINESTRA, controlli.disegna(frame_pulito))

            if cv2.waitKey(1) & 0xFF == 27:
                break
    finally:
        controlli.chiudi()
        ferma_cattura(processo)
        cv2.destroyAllWindows()

    sys.exit(0)


if __name__ == "__main__":
    main()
