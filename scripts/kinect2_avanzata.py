#!/usr/bin/env python3
"""
kinect2_avanzata.py — la camera "K" della Kinect Camera 2
-----------------------------------------------------------
È la "camera avanzata" del Kinect v1 riportata sul v2: una sola camera di
profondità con più MODALITA' di visualizzazione:

    Modo 0 -> SAGOMA: solo due livelli. Quello che sta tra la soglia VICINA e
              la soglia LONTANA diventa bianco pieno, tutto il resto nero.
              Niente gamma: la levetta sposta le due soglie.
    Modo 1 -> grigio con gamma        (come kinect2_profondita2.py)
    Modo 2 -> TURBO con gamma         (come kinect2_profondita_turbo2.py)

La camera parte SEMPRE dal modo 1. Il modo 0 si trova andando a sinistra.
Il selettore NON è ciclico: dal primo a sinistra e dall'ultimo a destra non
succede niente (la freccia diventa grigia).

Per aggiungere una modalità: scrivi una funzione render_xxx(depth) qui sotto
e aggiungila al dizionario MODALITA (le frecce e i tasti si adattano da soli).

Comandi:
  a tocco      -> foto / REC / pausa a destra, X per uscire, frecce < > in basso
                  per la modalità; in alto la levetta GAMMA (modi 1 e 2) oppure,
                  nel modo 0, la barra delle due soglie (trascini la maniglia
                  più vicina al dito)
  pulsanti     -> rosso REC/stop, verde pausa, LB foto, giallo esci,
                  BIANCO / NERO = modalità precedente / successiva,
                  pressione levetta = libera (per lo zoom che verrà)
                  modi 1-2: levetta destra/sinistra = gamma
                  modo 0:   levetta su/giù = soglia LONTANA (su = più lontano)
                            levetta destra/sinistra = soglia VICINA (destra = più lontano)
  tastiera     -> 0 / 1 / 2 modalità, + / - gamma, Esc esci
Salva in ~/Desktop/ki_la_visto/registrazioni/Kinect v2/ (video e foto).
"""
import cv2
import numpy as np

import kinect2_comune as k
from overlay_kinect2 import ControlliOverlayV2

stato = {"gamma": k.GAMMA_INIZIALE, "modalita": 1}

# --- Modo 0: SAGOMA ---------------------------------------------------------
# Le due soglie in millimetri dalla camera. Ogni volta che apri la K ripartono
# da questi valori.
SOGLIA_VICINA_INIZIALE = 500     # 50 cm: sotto il Kinect v2 non vede comunque
SOGLIA_LONTANA_INIZIALE = 2000   # 2 m
SOGLIA_MIN_MM = 500              # limiti entro cui si possono spostare
SOGLIA_MAX_MM = 4500
DISTANZA_MINIMA_TRA_SOGLIE = 100  # 10 cm: le soglie non si incrociano mai
VELOCITA_SOGLIA = 30             # mm per frame con la levetta tutta inclinata
# Pulizia dei bordi della sagoma (il Kinect fa un po' di "frangia" sui
# contorni): filtro mediano sulla maschera. 5 = leggero, 0 = spento.
FILTRO_SAGOMA = 5

soglie = {"vicina": SOGLIA_VICINA_INIZIALE, "lontana": SOGLIA_LONTANA_INIZIALE}


def _metti_soglia(quale, mm):
    if quale == "vicina":
        alto = soglie["lontana"] - DISTANZA_MINIMA_TRA_SOGLIE
        soglie["vicina"] = int(round(max(SOGLIA_MIN_MM, min(alto, mm))))
    else:
        basso = soglie["vicina"] + DISTANZA_MINIMA_TRA_SOGLIE
        soglie["lontana"] = int(round(max(basso, min(SOGLIA_MAX_MM, mm))))


def render_sagoma(depth):
    """Due soli livelli: dentro le soglie = bianco, fuori (o nessun dato) = nero."""
    dentro = (depth >= soglie["vicina"]) & (depth <= soglie["lontana"])
    maschera = dentro.astype(np.uint8) * 255
    if FILTRO_SAGOMA > 1:
        maschera = cv2.medianBlur(maschera, FILTRO_SAGOMA)
    return maschera


def render_grigio(depth):
    return k.profondita_gamma(depth, stato["gamma"])


def render_turbo(depth):
    return k.profondita_gamma_a_colori(depth, stato["gamma"], cv2.COLORMAP_TURBO)


MODALITA = {
    0: render_sagoma,
    1: render_grigio,
    2: render_turbo,
}
NOMI_MODALITA = {0: "SAGOMA", 1: "GRIGIO", 2: "TURBO"}  # mostrati accanto al numero
MODALITA_SENZA_GAMMA = {0}


def _metri(mm):
    return f"{mm / 1000:.2f}".replace(".", ",") + " m"


class ControlliK(ControlliOverlayV2):
    """L'overlay del v2, con in più la barra delle soglie al posto della
    gamma quando si è nel modo SAGOMA."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.soglia_trascinata = None  # "vicina" / "lontana" mentre il dito la tiene

    def _senza_gamma(self):
        return stato["modalita"] in MODALITA_SENZA_GAMMA

    # --- levetta analogica (chiamata da kinect2_comune a ogni frame) -------
    def usa_levetta(self, x, y):
        if not self._senza_gamma():
            return False  # modi 1-2: la levetta fa la gamma come sempre
        if x:
            _metti_soglia("vicina", soglie["vicina"] + x * VELOCITA_SOGLIA)
        if y:
            _metti_soglia("lontana", soglie["lontana"] + y * VELOCITA_SOGLIA)
        return True

    # --- barra delle soglie (stessa posizione della levetta gamma) ---------
    def _x_da_mm(self, mm):
        f = (mm - SOGLIA_MIN_MM) / (SOGLIA_MAX_MM - SOGLIA_MIN_MM)
        return int(self.gamma_x0 + f * (self.gamma_x1 - self.gamma_x0))

    def _mm_da_x(self, x):
        x = max(self.gamma_x0, min(self.gamma_x1, x))
        f = (x - self.gamma_x0) / (self.gamma_x1 - self.gamma_x0)
        return SOGLIA_MIN_MM + f * (SOGLIA_MAX_MM - SOGLIA_MIN_MM)

    def _disegna_soglie(self, frame):
        y = self.gamma_y
        x0, x1 = self.gamma_x0, self.gamma_x1
        xv, xl = self._x_da_mm(soglie["vicina"]), self._x_da_mm(soglie["lontana"])
        cv2.line(frame, (x0, y), (x1, y), (110, 110, 110), 3, cv2.LINE_AA)
        for x in (x0, x1):
            cv2.line(frame, (x, y - 6), (x, y + 6), (150, 150, 150), 2, cv2.LINE_AA)
        cv2.line(frame, (xv, y), (xl, y), (255, 255, 255), 5, cv2.LINE_AA)  # tratto "visto"
        for x in (xv, xl):
            cv2.circle(frame, (x, y), self.raggio_maniglia, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, (x, y), self.raggio_maniglia, (30, 30, 30), 2, cv2.LINE_AA)
        testo = f"{_metri(soglie['vicina'])}  -  {_metri(soglie['lontana'])}"
        (w, _), _ = cv2.getTextSize(testo, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        xt = (x0 + x1) // 2 - w // 2
        cv2.putText(frame, testo, (xt + 1, y - 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(frame, testo, (xt, y - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, "SOGLIE", (x1 + 12, y + 4), cv2.FONT_HERSHEY_SIMPLEX,
                    0.35, (210, 210, 210), 1, cv2.LINE_AA)

    def disegna(self, frame_bgr_pulito):
        if not self._senza_gamma():
            return super().disegna(frame_bgr_pulito)
        self.con_gamma = False
        try:
            frame = super().disegna(frame_bgr_pulito)
        finally:
            self.con_gamma = True
        self._disegna_soglie(frame)
        return frame

    def on_mouse(self, event, x, y, flags, userdata):
        if not self._senza_gamma():
            self.soglia_trascinata = None
            return super().on_mouse(event, x, y, flags, userdata)
        sulla_barra = abs(y - self.gamma_y) <= 18 and self.gamma_x0 - 15 <= x <= self.gamma_x1 + 15
        if event == cv2.EVENT_LBUTTONDOWN and sulla_barra:
            mm = self._mm_da_x(x)
            # prende la maniglia più vicina al dito
            if abs(mm - soglie["vicina"]) <= abs(mm - soglie["lontana"]):
                self.soglia_trascinata = "vicina"
            else:
                self.soglia_trascinata = "lontana"
            _metti_soglia(self.soglia_trascinata, mm)
            return
        if event == cv2.EVENT_MOUSEMOVE and self.soglia_trascinata:
            _metti_soglia(self.soglia_trascinata, self._mm_da_x(x))
            return
        if event == cv2.EVENT_LBUTTONUP and self.soglia_trascinata:
            self.soglia_trascinata = None
            return
        # tutto il resto (X, foto, REC, pausa, frecce) come sempre, senza gamma
        self.con_gamma = False
        try:
            super().on_mouse(event, x, y, flags, userdata)
        finally:
            self.con_gamma = True


controlli = ControlliK(larghezza=512, altezza=424,
                       con_gamma=True, stato_gamma=stato,
                       gamma_min=k.GAMMA_MIN, gamma_max=k.GAMMA_MAX,
                       con_modo=True, stato_modo=stato,
                       modo_min=min(MODALITA), modo_max=max(MODALITA),
                       nomi_modo=NOMI_MODALITA)

k.esegui_camera("Kinect 2 - K", colore=False, profondita=True,
                elabora=lambda f: MODALITA[stato["modalita"]](f["depth"]),
                overlay=controlli)
