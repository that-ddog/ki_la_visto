import freenect
import numpy as np
import cv2

NOME_FINESTRA = "Depth Camera 3"

# --- Parametri regolabili --------------------------------------------------
DISTANZA_MIN_MM = 400
DISTANZA_MAX_MM = 6000

# Esponente della curva di compensazione percettiva (vedi spiegazione sotto
# la funzione). 1.0 = nessuna correzione, mappatura lineare come in
# depth_grigio1.py. Valori più bassi (es. 0.4-0.6) spingono più dettaglio
# sulle distanze vicine, comprimendo quelle lontane. Prova a cambiarlo e
# vedere l'effetto: è il numero più interessante da smanettare qui.
GAMMA = 0.45

DIMENSIONE_FILTRO_RUMORE = 5


def depth_in_grigio(depth_mm):
    """
    Rispetto a depth_grigio1.py (mappatura lineare), qui applichiamo una
    curva di compensazione NON lineare (gamma) sulla distanza prima di
    convertirla in grigio.

    L'idea non è nostra: è la stessa logica alla base della tabella
    "t_gamma" usata in glview.c, il visualizzatore ufficiale della
    community OpenKinect (da cui derivano praticamente tutti i viewer e i
    wrapper Kinect v1 in giro, incluse le porte Python più diffuse). Loro
    la usano per dipingere la depth con un arcobaleno colorato; qui la
    adattiamo alla scala di grigi pura che vogliamo per il "mirino".

    Perché funziona meglio di una mappatura lineare: il Kinect v1 (luce
    strutturata) ha una precisione fisica molto più alta vicino (pochi mm
    di incertezza) che lontano (centimetri) — la relazione tra spostamento
    del pattern IR e distanza reale è intrinsecamente non lineare. Una
    mappatura lineare spreca quindi sfumature di grigio su distanze dove il
    sensore non ha comunque dettaglio vero da offrire. La curva gamma
    concentra il contrasto dove il sensore è davvero preciso: vicino.
    """
    maschera_valida = depth_mm > 0

    depth_clip = np.clip(depth_mm, DISTANZA_MIN_MM, DISTANZA_MAX_MM)
    v = (depth_clip - DISTANZA_MIN_MM) / (DISTANZA_MAX_MM - DISTANZA_MIN_MM)  # 0=vicino, 1=lontano

    v_corretta = np.power(v, GAMMA)
    grigio = 255 * (1 - v_corretta)
    grigio = grigio.astype(np.uint8)

    grigio[~maschera_valida] = 0  # nessun dato -> nero pulito

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
