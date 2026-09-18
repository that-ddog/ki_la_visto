import sys
import queue

import numpy as np
import cv2

from kinect_safe import avvia_cattura, ferma_cattura
from overlay_rec import ControlliOverlay
import input_fisico

NOME_FINESTRA = "Color Camera 2"

# --- Parametri regolabili --------------------------------------------------
DISTANZA_MIN_MM = 400
DISTANZA_MAX_MM = 6000

DIMENSIONE_FILTRO_RUMORE = 5

# Stessa curva gamma di depth_grigio3/4: la levetta la regola live.
stato = {"gamma": 0.45}
GAMMA_MIN = 0.2
GAMMA_MAX = 3.0

# Colormap di OpenCV da applicare. TURBO è il successore moderno di JET,
# pensato per essere percettivamente più uniforme (meno "bande" ingannevoli
# nel passaggio tra colori). Altre da provare, stesso identico codice, solo
# cambiando questa riga: cv2.COLORMAP_JET (il classico arcobaleno Kinect),
# cv2.COLORMAP_HOT (nero -> rosso -> giallo -> bianco, effetto "termico"),
# cv2.COLORMAP_VIRIDIS, cv2.COLORMAP_INFERNO.
COLORMAP = cv2.COLORMAP_HOT


def depth_in_colore(depth_mm):
    """
    Stessa logica di depth_grigio3.py (curva gamma non lineare, calibrazione
    mm, filtro anti-rumore) ma il risultato in scala di grigi viene passato
    a una colormap invece di essere mostrato così com'è. Vicino = valore
    alto (rosso/caldo con TURBO), lontano = valore basso (blu/freddo).
    """
    maschera_valida = depth_mm > 0

    depth_clip = np.clip(depth_mm, DISTANZA_MIN_MM, DISTANZA_MAX_MM)
    v = (depth_clip - DISTANZA_MIN_MM) / (DISTANZA_MAX_MM - DISTANZA_MIN_MM)  # 0=vicino, 1=lontano

    v_corretta = np.power(v, stato["gamma"])
    grigio = 255 * (1 - v_corretta)
    grigio = grigio.astype(np.uint8)

    grigio[~maschera_valida] = 0  # nessun dato -> estremo "lontano" (freddo)

    if DIMENSIONE_FILTRO_RUMORE > 1:
        grigio = cv2.medianBlur(grigio, DIMENSIONE_FILTRO_RUMORE)

    return cv2.applyColorMap(grigio, COLORMAP)


def cattura_un_frame():
    """Gira nel PROCESSO SEPARATO: legge un frame calibrato in mm dal Kinect.
    La conversione in colore resta nel processo principale, perché dipende
    da 'stato["gamma"]' che cambia live mentre l'utente trascina la levetta."""
    import freenect
    depth_mm, _ = freenect.sync_get_depth(format=freenect.DEPTH_MM)
    return depth_mm


def main():
    processo, coda = avvia_cattura(cattura_un_frame)
    controlli = ControlliOverlay(con_gamma=True, stato_gamma=stato,
                                  gamma_min=GAMMA_MIN, gamma_max=GAMMA_MAX)

    try:
        comandi = input_fisico.inizializza()
        input_fisico.collega_controlli_camera(comandi, controlli)
    except Exception as e:
        print(f"[INPUT] Pulsanti fisici non disponibili: {e}")

    print("Premi ESC nella finestra per uscire")
    cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(NOME_FINESTRA, controlli.on_mouse)

    ultimo_depth_mm = None
    schermata_attesa = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(schermata_attesa, "In attesa del Kinect...", (60, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    try:
        while True:
            try:
                ultimo_depth_mm = coda.get(timeout=0.05)
            except queue.Empty:
                pass

            if ultimo_depth_mm is not None:
                frame_pulito = depth_in_colore(ultimo_depth_mm)
            else:
                frame_pulito = schermata_attesa

            input_fisico.applica_levetta_gamma(controlli)
            controlli.gestisci_frame(frame_pulito)
            cv2.imshow(NOME_FINESTRA, controlli.disegna(frame_pulito))

            if cv2.waitKey(1) & 0xFF == 27 or controlli.richiesta_uscita:
                break
    finally:
        controlli.chiudi()
        input_fisico.termina()
        ferma_cattura(processo)
        cv2.destroyAllWindows()

    sys.exit(0)


if __name__ == "__main__":
    main()
