"""
overlay_kinect2.py
--------------------
Overlay REC / pausa / foto / X / levetta gamma per la Kinect Camera 2.

È lo STESSO overlay della Kinect Camera 1 (overlay_rec.py): stesse icone,
stessi comandi a tocco, stessi pulsanti fisici. Cambia solo dove e come
salva, per tenere separate le registrazioni del Kinect v2:

    video -> ~/Desktop/ki_la_visto/registrazioni/Kinect v2/video/v2_NNNN_DDMMYY.mp4
    foto  -> ~/Desktop/ki_la_visto/registrazioni/Kinect v2/foto/fotov2_NNNN_DDMMYY.jpg

overlay_rec.py NON viene modificato: qui lo estendiamo, così la Camera 1
resta esattamente com'era.

Durata dei video:
  Con il Kinect v1 gli fps erano sempre 30, quindi bastava scrivere ogni
  frame in un video a 30 fps. Col v2 sul Pi gli fps reali possono essere
  meno di 30 (dipende dalla GPU), e allora il video uscirebbe accelerato.
  Qui ogni frame viene scritto tante volte quante servono a coprire il tempo
  reale trascorso: il video dura sempre esattamente quanto la registrazione.
"""

import os
import time
from datetime import datetime

import cv2
import numpy as np

from overlay_rec import ControlliOverlay, Registrazione, _prossimo_numero, _percorso_univoco

CARTELLA_BASE_V2 = os.path.expanduser("~/Desktop/ki_la_visto/registrazioni/Kinect v2")
CARTELLA_VIDEO_V2 = os.path.join(CARTELLA_BASE_V2, "video")
CARTELLA_FOTO_V2 = os.path.join(CARTELLA_BASE_V2, "foto")
os.makedirs(CARTELLA_VIDEO_V2, exist_ok=True)
os.makedirs(CARTELLA_FOTO_V2, exist_ok=True)

PREFISSO_VIDEO = "v2"
PREFISSO_FOTO = "fotov2"
FPS_VIDEO_V2 = 30
SALTO_MASSIMO_S = 0.5  # se il Kinect si ferma, non "riempiamo" più di mezzo secondo


class RegistrazioneV2(Registrazione):
    def __init__(self, larghezza, altezza):
        super().__init__(larghezza, altezza)
        self.numero_clip = _prossimo_numero(CARTELLA_VIDEO_V2, PREFISSO_VIDEO)
        self._t_ultimo = None
        self._tempo_registrato = 0.0
        self._frame_scritti = 0

    def nome_prossima_clip(self):
        data = datetime.now().strftime("%d%m%y")
        return f"{PREFISSO_VIDEO}_{self.numero_clip:04d}_{data}"

    def avvia(self):
        if self.attiva:
            return
        base = self.nome_prossima_clip()
        self.percorso_clip = _percorso_univoco(CARTELLA_VIDEO_V2, base, "mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(self.percorso_clip, fourcc, FPS_VIDEO_V2,
                                      (self.larghezza, self.altezza))
        self.attiva = True
        self.in_pausa = False
        self.secondi_registrati = 0.0
        self._t_ultimo = None
        self._tempo_registrato = 0.0
        self._frame_scritti = 0
        print(f"[REC] Avviata: {self.percorso_clip}", flush=True)

    def scrivi_se_attiva(self, frame_bgr_pulito):
        if not self.attiva or self.writer is None:
            return
        ora = time.time()
        dt = 0.0 if self._t_ultimo is None else min(ora - self._t_ultimo, SALTO_MASSIMO_S)
        self._t_ultimo = ora  # aggiornato anche in pausa: il tempo in pausa non conta
        if self.in_pausa:
            return
        self._tempo_registrato += dt
        dovuti = int(self._tempo_registrato * FPS_VIDEO_V2) + 1
        while self._frame_scritti < dovuti:
            self.writer.write(frame_bgr_pulito)
            self._frame_scritti += 1
        self.secondi_registrati = self._frame_scritti / FPS_VIDEO_V2


def salva_foto_v2(frame_bgr_pulito):
    data = datetime.now().strftime("%d%m%y")
    numero = _prossimo_numero(CARTELLA_FOTO_V2, PREFISSO_FOTO)
    base = f"{PREFISSO_FOTO}_{numero:04d}_{data}"
    percorso = _percorso_univoco(CARTELLA_FOTO_V2, base, "jpg")
    cv2.imwrite(percorso, frame_bgr_pulito)
    print(f"[FOTO] Salvata: {percorso}", flush=True)


class ControlliOverlayV2(ControlliOverlay):
    """Come ControlliOverlay della Camera 1, ma registra con RegistrazioneV2
    e salva le foto nella cartella del Kinect v2.

    Selettore di modalità (con_modo=True, usato dalla camera K): invece delle
    freccine minuscole del v1, in basso al centro ci sono due pulsanti
    tondi grandi come le altre icone, con in mezzo "MODO N  NOME".
    nomi_modo: dict facoltativo {1: "GRIGIO", 2: "TURBO", ...}."""

    def __init__(self, nomi_modo=None, misura_registrazione=None, **kwargs):
        super().__init__(**kwargs)
        # misura_registrazione: (larghezza, altezza) dei video e delle foto,
        # se diversa da quella a schermo. Serve alla camera normale: registra
        # in Full HD ma mostra un'anteprima più piccola, così le icone
        # restano grandi. Se non la dai, registra alla misura dello schermo.
        self.misura_registrazione = misura_registrazione or (self.larghezza, self.altezza)
        self.registrazione = RegistrazioneV2(*self.misura_registrazione)
        self.nomi_modo = nomi_modo or {}
        if self.con_modo:
            # Le stesse variabili che usa on_mouse del v1 per il tocco sulle
            # frecce: cambiandole qui, anche il tocco segue i nuovi pulsanti.
            self.raggio_freccia = 17
            self.y_modo = self.altezza - 30
            self.x_modo_centro = self.larghezza // 2
            self.x_freccia_sx = self.x_modo_centro - 105
            self.x_freccia_dx = self.x_modo_centro + 105

    def disegna(self, frame_bgr_pulito):
        con_modo = self.con_modo
        self.con_modo = False  # le freccine piccole del v1 non le disegniamo
        try:
            frame = super().disegna(frame_bgr_pulito)
        finally:
            self.con_modo = con_modo
        if con_modo:
            self._disegna_selettore_modo(frame)
        return frame

    def _disegna_selettore_modo(self, frame):
        r = self.raggio_freccia
        y = self.y_modo
        x0, x1 = self.x_freccia_sx - r - 8, self.x_freccia_dx + r + 8
        y0, y1 = y - r - 6, y + r + 6
        # fascia scura semitrasparente, così si legge su qualunque immagine
        zona = frame[y0:y1, x0:x1]
        frame[y0:y1, x0:x1] = (zona * 0.45).astype(np.uint8)

        bianco = (255, 255, 255)
        for x, verso in ((self.x_freccia_sx, -1), (self.x_freccia_dx, +1)):
            cv2.circle(frame, (x, y), r, bianco, 2, cv2.LINE_AA)
            punta = np.array([[x + 7 * verso, y], [x - 5 * verso, y - 8], [x - 5 * verso, y + 8]])
            cv2.fillPoly(frame, [punta], bianco, cv2.LINE_AA)

        n = self.stato_modo["modalita"]
        testo = f"MODO {n}"
        nome = self.nomi_modo.get(n)
        if nome:
            testo += f"  {nome}"
        (w, h), _ = cv2.getTextSize(testo, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.putText(frame, testo, (self.x_modo_centro - w // 2, y + h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, bianco, 1, cv2.LINE_AA)

    def gestisci_frame(self, frame_bgr_pulito):
        self.registrazione.scrivi_se_attiva(frame_bgr_pulito)
        if self.richiesta_foto:
            salva_foto_v2(frame_bgr_pulito)
            self.richiesta_foto = False
