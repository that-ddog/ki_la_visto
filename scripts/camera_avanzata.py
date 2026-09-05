import sys
import queue

import numpy as np
import cv2

from kinect_safe import avvia_cattura, ferma_cattura
from overlay_rec import ControlliOverlay

NOME_FINESTRA = "Camera Avanzata"

LARGHEZZA, ALTEZZA = 640, 480

# =====================================================================
# STATO — modalità e gamma, entrambe modificabili live (tastiera 1-4/+/-
# oppure, ora, click sulle frecce e trascinamento della levetta a schermo).
# =====================================================================
stato = {
    "modalita": 3,
    "gamma": 0.45,
    "distanza_min_mm": 400,
    "distanza_max_mm": 6000,
    "filtro_rumore": 5,
}

GAMMA_MIN = 0.2
GAMMA_MAX = 3.0
GAMMA_PASSO = 0.05  # usato solo dalle scorciatoie da tastiera +/-


# =====================================================================
# Le 4 modalità di rendering (identiche a depth_grigio1-4.py nella logica).
# =====================================================================
def _render_modo_1_naive(depth_mm):
    validi = depth_mm[depth_mm > 0]
    massimo = validi.max() if validi.size > 0 else 1
    grigio = (depth_mm.astype(np.float32) / massimo) * 255
    return np.clip(grigio, 0, 255).astype(np.uint8)


def _render_modo_2_lineare(depth_mm):
    maschera_valida = depth_mm > 0
    mn, mx = stato["distanza_min_mm"], stato["distanza_max_mm"]
    depth_clip = np.clip(depth_mm, mn, mx)
    grigio = 255 - ((depth_clip - mn) / (mx - mn) * 255)
    grigio = grigio.astype(np.uint8)
    grigio[~maschera_valida] = 0
    return _applica_filtro(grigio)


def _render_modo_3_gamma_chiaro(depth_mm):
    maschera_valida = depth_mm > 0
    mn, mx = stato["distanza_min_mm"], stato["distanza_max_mm"]
    depth_clip = np.clip(depth_mm, mn, mx)
    v = (depth_clip - mn) / (mx - mn)
    v_corretta = np.power(v, stato["gamma"])
    grigio = 255 * (1 - v_corretta)
    grigio = grigio.astype(np.uint8)
    grigio[~maschera_valida] = 0
    return _applica_filtro(grigio)


def _render_modo_4_gamma_scuro(depth_mm):
    maschera_valida = depth_mm > 0
    mn, mx = stato["distanza_min_mm"], stato["distanza_max_mm"]
    depth_clip = np.clip(depth_mm, mn, mx)
    v = (depth_clip - mn) / (mx - mn)
    v_corretta = np.power(v, stato["gamma"])
    grigio = 255 * v_corretta
    grigio = grigio.astype(np.uint8)
    grigio[~maschera_valida] = 255
    return _applica_filtro(grigio)


def _applica_filtro(grigio):
    n = stato["filtro_rumore"]
    if n > 1:
        return cv2.medianBlur(grigio, n)
    return grigio


RENDER = {
    1: _render_modo_1_naive,
    2: _render_modo_2_lineare,
    3: _render_modo_3_gamma_chiaro,
    4: _render_modo_4_gamma_scuro,
}


def cattura_un_frame():
    import freenect
    depth_mm, _ = freenect.sync_get_depth(format=freenect.DEPTH_MM)
    return depth_mm


def main():
    processo, coda = avvia_cattura(cattura_un_frame)

    controlli = ControlliOverlay(
        larghezza=LARGHEZZA, altezza=ALTEZZA,
        con_gamma=True, stato_gamma=stato, gamma_min=GAMMA_MIN, gamma_max=GAMMA_MAX,
        con_modo=True, stato_modo=stato, modo_min=1, modo_max=4,
    )

    print("Premi ESC (o la X a schermo) per uscire.")
    print("Tasti: 1-4 = modalità, '+'/'-' = gamma (solo modi 3-4). Il resto si clicca a schermo.")

    cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(NOME_FINESTRA, controlli.on_mouse)

    ultimo_depth_mm = None
    schermata_attesa = np.zeros((ALTEZZA, LARGHEZZA), dtype=np.uint8)
    cv2.putText(schermata_attesa, "In attesa del Kinect...", (60, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2)

    try:
        while True:
            try:
                ultimo_depth_mm = coda.get(timeout=0.05)
            except queue.Empty:
                pass

            if ultimo_depth_mm is not None:
                grigio = RENDER[stato["modalita"]](ultimo_depth_mm)
            else:
                grigio = schermata_attesa

            frame_pulito = cv2.cvtColor(grigio, cv2.COLOR_GRAY2BGR)
            controlli.gestisci_frame(frame_pulito)
            cv2.imshow(NOME_FINESTRA, controlli.disegna(frame_pulito))

            tasto = cv2.waitKey(1) & 0xFF
            if tasto == 27 or controlli.richiesta_uscita:
                break
            elif tasto in (ord('1'), ord('2'), ord('3'), ord('4')):
                stato["modalita"] = int(chr(tasto))
                print(f"[STATO] Modalità -> {stato['modalita']}")
            elif tasto in (ord('+'), ord('=')):
                stato["gamma"] = round(min(GAMMA_MAX, stato["gamma"] + GAMMA_PASSO), 2)
            elif tasto == ord('-'):
                stato["gamma"] = round(max(GAMMA_MIN, stato["gamma"] - GAMMA_PASSO), 2)
    finally:
        controlli.chiudi()  # se una REC era attiva, la salva prima di uscire
        ferma_cattura(processo)
        cv2.destroyAllWindows()

    sys.exit(0)


if __name__ == "__main__":
    main()
