import freenect
import numpy as np
import cv2

NOME_FINESTRA = "Depth Camera 1"

# --- Parametri regolabili --------------------------------------------------
# Range di distanza (in millimetri) su cui vogliamo un buon contrasto.
# Il Kinect v1 è affidabile all'incirca tra 500mm e 3000-3500mm: sotto o
# sopra questi valori il sensore restituisce 0 ("nessun dato"), è un limite
# fisico del sensore, non un bug. Puoi aggiustare questi due numeri per
# stringere/allargare la zona a fuoco visivo.
DISTANZA_MIN_MM = 500
DISTANZA_MAX_MM = 3000

# Riduce il rumore "sale e pepe" tipico del sensore Kinect v1.
# Deve essere un numero dispari; metti 0 o 1 per disattivare il filtro.
DIMENSIONE_FILTRO_RUMORE = 5


def depth_in_grigio(depth_mm):
    """
    Converte una matrice di depth in millimetri in un'immagine grigia a 8 bit:
      - contrasto stabile, basato su un range fisso
      - pixel senza dato valido (troppo vicino/lontano) resi neri
      - filtro mediano leggero per ripulire il rumore pixel-per-pixel
    """
    maschera_valida = depth_mm > 0

    depth_clip = np.clip(depth_mm, DISTANZA_MIN_MM, DISTANZA_MAX_MM)
    grigio = 255 - ((depth_clip - DISTANZA_MIN_MM) /
                     (DISTANZA_MAX_MM - DISTANZA_MIN_MM) * 255)
    grigio = grigio.astype(np.uint8)

    grigio[~maschera_valida] = 0

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
