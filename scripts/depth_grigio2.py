import sys
import queue

import numpy as np
import cv2

from kinect_safe import avvia_cattura, ferma_cattura
from overlay_rec import ControlliOverlay

NOME_FINESTRA = "Depth Camera 2"

# --- Parametri regolabili --------------------------------------------------
DISTANZA_MIN_MM = 400
DISTANZA_MAX_MM = 6000

DIMENSIONE_FILTRO_RUMORE = 5


def depth_in_grigio(depth_mm):
    """Mappatura lineare: contrasto stabile su range fisso, pixel senza dato
    valido resi neri, filtro mediano per il rumore pixel-per-pixel."""
    maschera_valida = depth_mm > 0

    depth_clip = np.clip(depth_mm, DISTANZA_MIN_MM, DISTANZA_MAX_MM)
    grigio = 255 - ((depth_clip - DISTANZA_MIN_MM) /
                     (DISTANZA_MAX_MM - DISTANZA_MIN_MM) * 255)
    grigio = grigio.astype(np.uint8)

    grigio[~maschera_valida] = 0

    if DIMENSIONE_FILTRO_RUMORE > 1:
        grigio = cv2.medianBlur(grigio, DIMENSIONE_FILTRO_RUMORE)

    return grigio


def cattura_un_frame():
    """Gira nel PROCESSO SEPARATO: legge un frame calibrato in mm dal Kinect
    e lo converte già in grigio, così il processo principale deve solo
    mostrarlo."""
    import freenect
    depth_mm, _ = freenect.sync_get_depth(format=freenect.DEPTH_MM)
    return depth_in_grigio(depth_mm)


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
                pass

            frame_pulito = cv2.cvtColor(ultimo_frame_grigio, cv2.COLOR_GRAY2BGR)
            controlli.gestisci_frame(frame_pulito)
            cv2.imshow(NOME_FINESTRA, controlli.disegna(frame_pulito))

            if cv2.waitKey(1) & 0xFF == 27 or controlli.richiesta_uscita:
                break
    finally:
        controlli.chiudi()
        ferma_cattura(processo)
        cv2.destroyAllWindows()

    sys.exit(0)


if __name__ == "__main__":
    main()
