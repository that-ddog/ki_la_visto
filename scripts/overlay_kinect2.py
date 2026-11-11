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
    e salva le foto nella cartella del Kinect v2."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.registrazione = RegistrazioneV2(self.larghezza, self.altezza)

    def gestisci_frame(self, frame_bgr_pulito):
        self.registrazione.scrivi_se_attiva(frame_bgr_pulito)
        if self.richiesta_foto:
            salva_foto_v2(frame_bgr_pulito)
            self.richiesta_foto = False
