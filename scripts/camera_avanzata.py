import sys
import os
import re
import time
import queue
from datetime import datetime

import numpy as np
import cv2

from kinect_safe import avvia_cattura, ferma_cattura

NOME_FINESTRA = "Camera Avanzata"

LARGHEZZA, ALTEZZA = 640, 480
FPS_VIDEO = 20  # stima; se il playback sembra troppo lento/veloce, aggiusta questo numero

CARTELLA_VIDEO = os.path.expanduser("~/Desktop/ki_la_visto/registrazioni/video")
CARTELLA_FOTO = os.path.expanduser("~/Desktop/ki_la_visto/registrazioni/foto")
os.makedirs(CARTELLA_VIDEO, exist_ok=True)
os.makedirs(CARTELLA_FOTO, exist_ok=True)

# =====================================================================
# STATO — tutto ciò che si può cambiare "live" (modalità, gamma) vive qui.
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


# =====================================================================
# Nomi file: clip_NNNN_GGMMAA / foto_NNNN_GGMMAA, con contatore che scansiona
# la cartella a ogni avvio (robusto ai riavvii, non serve salvare uno stato
# a parte) e un "(1)" di sicurezza per le collisioni improbabili.
# =====================================================================
def _prossimo_numero(cartella, prefisso):
    pattern = re.compile(rf"^{re.escape(prefisso)}_(\d{{4}})_\d{{6}}")
    massimo = -1
    for nome in os.listdir(cartella):
        m = pattern.match(nome)
        if m:
            massimo = max(massimo, int(m.group(1)))
    return massimo + 1


def _percorso_univoco(cartella, base, estensione):
    candidato = os.path.join(cartella, f"{base}.{estensione}")
    i = 1
    while os.path.exists(candidato):
        candidato = os.path.join(cartella, f"{base}({i}).{estensione}")
        i += 1
    return candidato


# =====================================================================
# Registrazione: REC/stop/pausa/play, un file per clip, numerazione
# progressiva che continua a salire (non si azzera mai per il giorno).
# =====================================================================
class Registrazione:
    def __init__(self):
        self.attiva = False
        self.in_pausa = False
        self.writer = None
        self.percorso_clip = None
        self.numero_clip = _prossimo_numero(CARTELLA_VIDEO, "clip")
        self.secondi_registrati = 0.0

    def nome_prossima_clip(self):
        data = datetime.now().strftime("%d%m%y")
        return f"clip_{self.numero_clip:04d}_{data}"

    def avvia(self):
        if self.attiva:
            return
        base = self.nome_prossima_clip()
        self.percorso_clip = _percorso_univoco(CARTELLA_VIDEO, base, "mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(self.percorso_clip, fourcc, FPS_VIDEO, (LARGHEZZA, ALTEZZA))
        self.attiva = True
        self.in_pausa = False
        self.secondi_registrati = 0.0
        print(f"[REC] Avviata: {self.percorso_clip}")

    def ferma(self):
        if not self.attiva:
            return
        if self.writer is not None:
            self.writer.release()
        print(f"[REC] Fermata: {self.percorso_clip}  ({self.secondi_registrati:.1f}s)")
        self.attiva = False
        self.in_pausa = False
        self.writer = None
        self.percorso_clip = None
        self.numero_clip += 1

    def metti_in_pausa(self):
        if self.attiva:
            self.in_pausa = True

    def riprendi(self):
        if self.attiva:
            self.in_pausa = False

    def scrivi_se_attiva(self, frame_bgr_pulito):
        if self.attiva and not self.in_pausa and self.writer is not None:
            self.writer.write(frame_bgr_pulito)
            self.secondi_registrati += 1.0 / FPS_VIDEO

    def nome_da_mostrare(self):
        if self.attiva and self.percorso_clip:
            return os.path.splitext(os.path.basename(self.percorso_clip))[0]
        return self.nome_prossima_clip()


def salva_foto(frame_bgr_pulito):
    data = datetime.now().strftime("%d%m%y")
    numero = _prossimo_numero(CARTELLA_FOTO, "foto")
    base = f"foto_{numero:04d}_{data}"
    percorso = _percorso_univoco(CARTELLA_FOTO, base, "jpg")
    cv2.imwrite(percorso, frame_bgr_pulito)
    print(f"[FOTO] Salvata: {percorso}")


# =====================================================================
# Zone cliccabili (coordinate nello spazio dell'immagine 640x480).
# =====================================================================
X_ICONE = 605
RAGGIO_ICONA = 22
Y_FOTO = 60
Y_REC = 240
Y_PAUSA = 420

X_LEVETTA = 30
Y_LEVETTA_TOP = 80
Y_LEVETTA_BOTTOM = 400
RAGGIO_MANIGLIA = 10

registrazione = Registrazione()
richiesta_foto = {"flag": False}
trascinamento_levetta = {"attivo": False}


def _dentro_cerchio(x, y, cx, cy, raggio):
    return (x - cx) ** 2 + (y - cy) ** 2 <= raggio ** 2


def _aggiorna_gamma_da_y(y):
    y_c = max(Y_LEVETTA_TOP, min(Y_LEVETTA_BOTTOM, y))
    frazione = (y_c - Y_LEVETTA_TOP) / (Y_LEVETTA_BOTTOM - Y_LEVETTA_TOP)  # 0 in alto, 1 in basso
    stato["gamma"] = round(GAMMA_MAX - frazione * (GAMMA_MAX - GAMMA_MIN), 3)


def on_mouse(event, x, y, flags, userdata):
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"[CLICK] x={x} y={y}")  # utile per calibrare se le zone non combaciano

        if _dentro_cerchio(x, y, X_ICONE, Y_FOTO, RAGGIO_ICONA):
            richiesta_foto["flag"] = True

        elif _dentro_cerchio(x, y, X_ICONE, Y_REC, RAGGIO_ICONA):
            if registrazione.attiva:
                registrazione.ferma()
            else:
                registrazione.avvia()

        elif registrazione.attiva and _dentro_cerchio(x, y, X_ICONE, Y_PAUSA, RAGGIO_ICONA):
            if registrazione.in_pausa:
                registrazione.riprendi()
            else:
                registrazione.metti_in_pausa()

        elif abs(x - X_LEVETTA) < 25 and Y_LEVETTA_TOP - 15 <= y <= Y_LEVETTA_BOTTOM + 15:
            trascinamento_levetta["attivo"] = True
            _aggiorna_gamma_da_y(y)

    elif event == cv2.EVENT_MOUSEMOVE:
        if trascinamento_levetta["attivo"]:
            _aggiorna_gamma_da_y(y)

    elif event == cv2.EVENT_LBUTTONUP:
        trascinamento_levetta["attivo"] = False


# =====================================================================
# Overlay: disegna tutti gli elementi SOLO per la visualizzazione a
# schermo. Il file salvato (video o foto) usa il frame pulito, senza
# nessuno di questi elementi sopra.
# =====================================================================
def disegna_overlay(frame_bgr_pulito):
    frame = frame_bgr_pulito.copy()

    # --- Levetta gamma ---
    cv2.line(frame, (X_LEVETTA, Y_LEVETTA_TOP), (X_LEVETTA, Y_LEVETTA_BOTTOM), (150, 150, 150), 3)
    frazione = (GAMMA_MAX - stato["gamma"]) / (GAMMA_MAX - GAMMA_MIN)
    y_maniglia = int(Y_LEVETTA_TOP + frazione * (Y_LEVETTA_BOTTOM - Y_LEVETTA_TOP))
    cv2.circle(frame, (X_LEVETTA, y_maniglia), RAGGIO_MANIGLIA, (255, 255, 255), -1)
    cv2.circle(frame, (X_LEVETTA, y_maniglia), RAGGIO_MANIGLIA, (30, 30, 30), 2)

    # --- Foto: cerchio bianco vuoto ---
    cv2.circle(frame, (X_ICONE, Y_FOTO), RAGGIO_ICONA, (255, 255, 255), 2)

    # --- Rec / stop ---
    if registrazione.attiva:
        lato = int(RAGGIO_ICONA * 1.1)
        cv2.rectangle(frame,
                      (X_ICONE - lato // 2, Y_REC - lato // 2),
                      (X_ICONE + lato // 2, Y_REC + lato // 2),
                      (0, 0, 255), -1)
    else:
        cv2.circle(frame, (X_ICONE, Y_REC), RAGGIO_ICONA, (0, 0, 255), -1)

    # --- Pausa / play: visibile solo durante la registrazione ---
    if registrazione.attiva:
        # Cerchio guida sempre presente (come per REC e FOTO), così l'icona
        # non rischia di sparire nel rumore dell'immagine sotto.
        cv2.circle(frame, (X_ICONE, Y_PAUSA), RAGGIO_ICONA, (255, 255, 255), 2)

        if registrazione.in_pausa:
            # triangolo "play" pieno
            pts = np.array([
                [X_ICONE - 8, Y_PAUSA - 12],
                [X_ICONE - 8, Y_PAUSA + 12],
                [X_ICONE + 12, Y_PAUSA],
            ])
            cv2.fillPoly(frame, [pts], (255, 255, 255))
        else:
            # due barrette "pausa"
            cv2.rectangle(frame, (X_ICONE - 10, Y_PAUSA - 11), (X_ICONE - 3, Y_PAUSA + 11), (255, 255, 255), -1)
            cv2.rectangle(frame, (X_ICONE + 3, Y_PAUSA - 11), (X_ICONE + 10, Y_PAUSA + 11), (255, 255, 255), -1)

    # --- Icona in alto a sinistra: pallino REC lampeggiante o simbolo pausa fisso ---
    if registrazione.attiva:
        if registrazione.in_pausa:
            cv2.rectangle(frame, (14, 13), (18, 27), (0, 0, 255), -1)
            cv2.rectangle(frame, (22, 13), (26, 27), (0, 0, 255), -1)
        elif int(time.time() * 2) % 2 == 0:  # lampeggia ogni ~0.5s
            cv2.circle(frame, (20, 20), 7, (0, 0, 255), -1)

    # --- Minutaggio: solo durante la registrazione ---
    if registrazione.attiva:
        minuti = int(registrazione.secondi_registrati // 60)
        secondi = int(registrazione.secondi_registrati % 60)
        testo_tempo = f"{minuti}:{secondi:02d}"
        cv2.putText(frame, testo_tempo, (LARGHEZZA // 2 - 30, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    # --- Nome clip (basso a sinistra, piccolo) ---
    cv2.putText(frame, registrazione.nome_da_mostrare(), (10, ALTEZZA - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (210, 210, 210), 1)

    # --- Modalità corrente (basso a destra, piccolo) ---
    testo_modo = f"Modo {stato['modalita']}"
    cv2.putText(frame, testo_modo, (LARGHEZZA - 90, ALTEZZA - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (210, 210, 210), 1)

    return frame


def cattura_un_frame():
    import freenect
    depth_mm, _ = freenect.sync_get_depth(format=freenect.DEPTH_MM)
    return depth_mm


def main():
    processo, coda = avvia_cattura(cattura_un_frame)

    print("Premi ESC per uscire.")
    print("Tasti: 1-4 = modalità, '+'/'-' = gamma (solo modi 3-4). Il resto si clicca a schermo.")

    cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(NOME_FINESTRA, on_mouse)

    ultimo_depth_mm = None
    schermata_attesa = np.zeros((ALTEZZA, LARGHEZZA, 3), dtype=np.uint8)
    cv2.putText(schermata_attesa, "In attesa del Kinect...", (60, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    try:
        while True:
            try:
                ultimo_depth_mm = coda.get(timeout=0.05)
            except queue.Empty:
                pass

            if ultimo_depth_mm is not None:
                grigio = RENDER[stato["modalita"]](ultimo_depth_mm)
                frame_pulito = cv2.cvtColor(grigio, cv2.COLOR_GRAY2BGR)
            else:
                frame_pulito = schermata_attesa

            # Il video registrato usa il frame PULITO, senza overlay.
            registrazione.scrivi_se_attiva(frame_pulito)

            if richiesta_foto["flag"]:
                salva_foto(frame_pulito)
                richiesta_foto["flag"] = False

            cv2.imshow(NOME_FINESTRA, disegna_overlay(frame_pulito))

            tasto = cv2.waitKey(1) & 0xFF
            if tasto == 27:  # ESC
                break
            elif tasto in (ord('1'), ord('2'), ord('3'), ord('4')):
                stato["modalita"] = int(chr(tasto))
                print(f"[STATO] Modalità -> {stato['modalita']}")
            elif tasto in (ord('+'), ord('=')):
                stato["gamma"] = round(min(GAMMA_MAX, stato["gamma"] + GAMMA_PASSO), 2)
            elif tasto == ord('-'):
                stato["gamma"] = round(max(GAMMA_MIN, stato["gamma"] - GAMMA_PASSO), 2)
    finally:
        registrazione.ferma()  # se esci con REC ancora attiva, chiudiamo il file per bene
        ferma_cattura(processo)
        cv2.destroyAllWindows()

    sys.exit(0)


if __name__ == "__main__":
    main()
