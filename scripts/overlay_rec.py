"""
overlay_rec.py
----------------
Overlay e controlli di registrazione (REC/pausa/foto, più la levetta gamma
opzionale) condivisi da tutti gli script che mostrano un flusso Kinect a
schermo intero. Un unico posto dove vive questa logica, così ogni script
depth/video la eredita gratis invece di duplicarla.

Uso tipico in uno script:

    from overlay_rec import ControlliOverlay

    controlli = ControlliOverlay(con_gamma=True, stato_gamma=stato)  # o con_gamma=False
    cv2.namedWindow(NOME_FINESTRA, ...)
    cv2.setMouseCallback(NOME_FINESTRA, controlli.on_mouse)

    while True:
        frame_pulito = ...  # il tuo frame BGR, SENZA overlay
        controlli.gestisci_frame(frame_pulito)          # scrive video / salva foto
        cv2.imshow(NOME_FINESTRA, controlli.disegna(frame_pulito))
        ...

    controlli.chiudi()  # alla fine, per chiudere bene un'eventuale REC aperta
"""

import os
import re
import time
from datetime import datetime

import numpy as np
import cv2

LARGHEZZA_DEFAULT, ALTEZZA_DEFAULT = 640, 480
FPS_VIDEO = 20  # stima; se il playback sembra troppo lento/veloce, aggiusta questo numero

CARTELLA_VIDEO = os.path.expanduser("~/Desktop/ki_la_visto/registrazioni/video")
CARTELLA_FOTO = os.path.expanduser("~/Desktop/ki_la_visto/registrazioni/foto")
os.makedirs(CARTELLA_VIDEO, exist_ok=True)
os.makedirs(CARTELLA_FOTO, exist_ok=True)


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


class Registrazione:
    """REC/stop/pausa/play, un file per clip. Il numero clip è condiviso
    (scansiona la stessa cartella) qualunque script stia registrando, così
    la numerazione resta unica e progressiva ovunque tu registri da."""

    def __init__(self, larghezza=LARGHEZZA_DEFAULT, altezza=ALTEZZA_DEFAULT):
        self.larghezza = larghezza
        self.altezza = altezza
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
        self.writer = cv2.VideoWriter(self.percorso_clip, fourcc, FPS_VIDEO, (self.larghezza, self.altezza))
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


class ControlliOverlay:
    """
    Incapsula le icone cliccabili (REC/foto/pausa) e, se richiesto, la
    levetta gamma. Un'istanza per script.
    """

    def __init__(self, larghezza=LARGHEZZA_DEFAULT, altezza=ALTEZZA_DEFAULT,
                 con_gamma=False, stato_gamma=None, gamma_min=0.2, gamma_max=3.0):
        self.larghezza = larghezza
        self.altezza = altezza
        self.registrazione = Registrazione(larghezza, altezza)
        self.richiesta_foto = False
        self.trascinamento_levetta = False

        self.con_gamma = con_gamma
        self.stato_gamma = stato_gamma  # dict con chiave "gamma", del chiamante
        self.gamma_min = gamma_min
        self.gamma_max = gamma_max

        # Geometria icone, in coordinate immagine (si adatta a larghezza/altezza)
        self.x_icone = larghezza - 35
        self.raggio_icona = 22
        self.y_foto = 60
        self.y_rec = altezza // 2
        self.y_pausa = altezza - 60

        self.x_levetta = 30
        self.y_levetta_top = 80
        self.y_levetta_bottom = altezza - 80
        self.raggio_maniglia = 10

    # --- interazione -----------------------------------------------------
    def _dentro_cerchio(self, x, y, cx, cy, raggio):
        return (x - cx) ** 2 + (y - cy) ** 2 <= raggio ** 2

    def _aggiorna_gamma_da_y(self, y):
        if not self.con_gamma:
            return
        y_c = max(self.y_levetta_top, min(self.y_levetta_bottom, y))
        frazione = (y_c - self.y_levetta_top) / (self.y_levetta_bottom - self.y_levetta_top)
        self.stato_gamma["gamma"] = round(self.gamma_max - frazione * (self.gamma_max - self.gamma_min), 3)

    def on_mouse(self, event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"[CLICK] x={x} y={y}")
            if self._dentro_cerchio(x, y, self.x_icone, self.y_foto, self.raggio_icona):
                self.richiesta_foto = True
            elif self._dentro_cerchio(x, y, self.x_icone, self.y_rec, self.raggio_icona):
                if self.registrazione.attiva:
                    self.registrazione.ferma()
                else:
                    self.registrazione.avvia()
            elif self.registrazione.attiva and self._dentro_cerchio(x, y, self.x_icone, self.y_pausa, self.raggio_icona):
                if self.registrazione.in_pausa:
                    self.registrazione.riprendi()
                else:
                    self.registrazione.metti_in_pausa()
            elif self.con_gamma and abs(x - self.x_levetta) < 25 and self.y_levetta_top - 15 <= y <= self.y_levetta_bottom + 15:
                self.trascinamento_levetta = True
                self._aggiorna_gamma_da_y(y)
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.trascinamento_levetta:
                self._aggiorna_gamma_da_y(y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.trascinamento_levetta = False

    # --- da chiamare nel ciclo principale ---------------------------------
    def gestisci_frame(self, frame_bgr_pulito):
        """Una volta per frame: scrive nel video se in REC, salva la foto se
        richiesta. Non disegna nulla (per quello vedi disegna())."""
        self.registrazione.scrivi_se_attiva(frame_bgr_pulito)
        if self.richiesta_foto:
            salva_foto(frame_bgr_pulito)
            self.richiesta_foto = False

    def disegna(self, frame_bgr_pulito):
        """Ritorna una COPIA del frame con sopra tutti gli elementi
        cliccabili — usa questa per cv2.imshow, non per salvare."""
        frame = frame_bgr_pulito.copy()
        r = self.registrazione

        if self.con_gamma:
            cv2.line(frame, (self.x_levetta, self.y_levetta_top),
                      (self.x_levetta, self.y_levetta_bottom), (150, 150, 150), 3)
            frazione = (self.gamma_max - self.stato_gamma["gamma"]) / (self.gamma_max - self.gamma_min)
            y_m = int(self.y_levetta_top + frazione * (self.y_levetta_bottom - self.y_levetta_top))
            cv2.circle(frame, (self.x_levetta, y_m), self.raggio_maniglia, (255, 255, 255), -1)
            cv2.circle(frame, (self.x_levetta, y_m), self.raggio_maniglia, (30, 30, 30), 2)

        # Foto
        cv2.circle(frame, (self.x_icone, self.y_foto), self.raggio_icona, (255, 255, 255), 2)

        # Rec / stop
        if r.attiva:
            lato = int(self.raggio_icona * 1.1)
            cv2.rectangle(frame,
                          (self.x_icone - lato // 2, self.y_rec - lato // 2),
                          (self.x_icone + lato // 2, self.y_rec + lato // 2),
                          (0, 0, 255), -1)
        else:
            cv2.circle(frame, (self.x_icone, self.y_rec), self.raggio_icona, (0, 0, 255), -1)

        # Pausa / play (con cerchio guida sempre visibile, come rec/foto)
        if r.attiva:
            cv2.circle(frame, (self.x_icone, self.y_pausa), self.raggio_icona, (255, 255, 255), 2)
            if r.in_pausa:
                pts = np.array([
                    [self.x_icone - 8, self.y_pausa - 12],
                    [self.x_icone - 8, self.y_pausa + 12],
                    [self.x_icone + 12, self.y_pausa],
                ])
                cv2.fillPoly(frame, [pts], (255, 255, 255))
            else:
                cv2.rectangle(frame, (self.x_icone - 10, self.y_pausa - 11),
                              (self.x_icone - 3, self.y_pausa + 11), (255, 255, 255), -1)
                cv2.rectangle(frame, (self.x_icone + 3, self.y_pausa - 11),
                              (self.x_icone + 10, self.y_pausa + 11), (255, 255, 255), -1)

        # Pallino REC lampeggiante / simbolo pausa fisso, alto a sinistra
        if r.attiva:
            if r.in_pausa:
                cv2.rectangle(frame, (14, 13), (18, 27), (0, 0, 255), -1)
                cv2.rectangle(frame, (22, 13), (26, 27), (0, 0, 255), -1)
            elif int(time.time() * 2) % 2 == 0:
                cv2.circle(frame, (20, 20), 7, (0, 0, 255), -1)

        # Minutaggio, solo durante la REC
        if r.attiva:
            minuti = int(r.secondi_registrati // 60)
            secondi = int(r.secondi_registrati % 60)
            cv2.putText(frame, f"{minuti}:{secondi:02d}", (self.larghezza // 2 - 30, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Nome clip, basso a sinistra
        cv2.putText(frame, r.nome_da_mostrare(), (10, self.altezza - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (210, 210, 210), 1)

        return frame

    def chiudi(self):
        """Da chiamare all'uscita dello script: se una REC era ancora
        aperta, la chiude per bene invece di lasciare un file corrotto."""
        self.registrazione.ferma()
