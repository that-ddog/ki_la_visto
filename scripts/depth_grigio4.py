import freenect
import numpy as np
import cv2

NOME_FINESTRA = "Depth Camera 4"

# --- Parametri regolabili --------------------------------------------------
DISTANZA_MIN_MM = 400
DISTANZA_MAX_MM = 6000

# Stesso esponente di depth_grigio3.py: vedi lì per la spiegazione completa
# della curva gamma. Qui cambia solo la polarità del grigio.
GAMMA = 0.45

DIMENSIONE_FILTRO_RUMORE = 5


def depth_in_grigio(depth_mm):
    """
    Identica a depth_grigio3.py nella logica (curva gamma non lineare, presa
    dall'esempio ufficiale OpenKinect glview.c, per concentrare il dettaglio
    dove il sensore è davvero preciso: vicino) — ma con la polarità del
    grigio INVERTITA: qui vicino = scuro, lontano = chiaro, per riprendere
    la "fantasia" cromatica di depth_grigio1.py che preferisci.
    """
    maschera_valida = depth_mm > 0

    depth_clip = np.clip(depth_mm, DISTANZA_MIN_MM, DISTANZA_MAX_MM)
    v = (depth_clip - DISTANZA_MIN_MM) / (DISTANZA_MAX_MM - DISTANZA_MIN_MM)  # 0=vicino, 1=lontano

    v_corretta = np.power(v, GAMMA)
    grigio = 255 * v_corretta  # <-- unica differenza rispetto a grigio3: niente "1 -"
    grigio = grigio.astype(np.uint8)

    grigio[~maschera_valida] = 255  # nessun dato -> stesso colore del "lontano" (bianco), non del "vicino"

    if DIMENSIONE_FILTRO_RUMORE > 1:
        grigio = cv2.medianBlur(grigio, DIMENSIONE_FILTRO_RUMORE)

    return grigio


print("Premi ESC nella finestra per uscire")

cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

while True:
    depth_mm, _ = freenect.sync_get_depth(format=freenect.DEPTH_MM)
    grigio = depth_in_grigio(depth_mm)
    cv2.imshow(NOME_FINESTRA, grigio)
    if cv2.waitKey(1) == 27:
        break

cv2.destroyAllWindows()
