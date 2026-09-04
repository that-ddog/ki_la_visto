import sys
import queue

import numpy as np
import cv2

from kinect_safe import avvia_cattura, ferma_cattura
from overlay_rec import ControlliOverlay

NOME_FINESTRA = "Depth Camera 3"

# --- Parametri regolabili --------------------------------------------------
DISTANZA_MIN_MM = 400
DISTANZA_MAX_MM = 6000

DIMENSIONE_FILTRO_RUMORE = 5

# La gamma ora vive in un dizionario (non più una costante fissa): è quello
# che la levetta a schermo modifica live mentre lo script gira. Il valore
# iniziale è lo stesso di prima.
stato = {"gamma": 0.45}
GAMMA_MIN = 0.2
GAMMA_MAX = 3.0


def depth_in_grigio(depth_mm):
    """Curva gamma non lineare (presa dall'esempio ufficiale OpenKinect
    glview.c): concentra il contrasto dove il sensore è più preciso
    (vicino = chiaro, lontano = scuro)."""
    maschera_valida = depth_mm > 0

    depth_clip = np.clip(depth_mm, DISTANZA_MIN_MM, DISTANZA_MAX_MM)
    v = (depth_clip - DISTANZA_MIN_MM) / (DISTANZA_MAX_MM - DISTANZA_MIN_MM)  # 0=vicino, 1=lontano

    v_corretta = np.power(v, stato["gamma"])
    grigio = 255 * (1 - v_corretta)
    grigio = grigio.astype(np.uint8)

    grigio[~maschera_valida] = 0  # nessun dato -> stesso colore del "lontano" (nero)

    if DIMENSIONE_FILTRO_RUMORE > 1:
        grigio = cv2.medianBlur(grigio, DIMENSIONE_FILTRO_RUMORE)

    return grigio


def cattura_un_frame():
    """Gira nel PROCESSO SEPARATO: legge un frame calibrato in mm dal Kinect.
    La conversione in grigio resta nel processo principale, perché dipende
    da 'stato[\"gamma\"]' che cambia live mentre l'utente trascina la
    levetta."""
    import freenect
    depth_mm, _ = freenect.sync_get_depth(format=freenect.DEPTH_MM)
    return depth_mm


def main():
    processo, coda = avvia_cattura(cattura_un_frame)
    controlli = ControlliOverlay(con_gamma=True, stato_gamma=stato,
                                  gamma_min=GAMMA_MIN, gamma_max=GAMMA_MAX)

    print("Premi ESC nella finestra per uscire")
    cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(NOME_FINESTRA, controlli.on_mouse)

    ultimo_depth_mm = None
    schermata_attesa = np.zeros((480, 640), dtype=np.uint8)
    cv2.putText(schermata_attesa, "In attesa del Kinect...", (60, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2)

    try:
        while True:
            try:
                ultimo_depth_mm = coda.get(timeout=0.05)
            except queue.Empty:
                pass

            if ultimo_depth_mm is not None:
                grigio = depth_in_grigio(ultimo_depth_mm)
            else:
                grigio = schermata_attesa

            frame_pulito = cv2.cvtColor(grigio, cv2.COLOR_GRAY2BGR)
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
