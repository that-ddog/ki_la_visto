#!/usr/bin/env python3
"""
kinect2_avanzata.py — la camera "K" della Kinect Camera 2
-----------------------------------------------------------
È la "camera avanzata" del Kinect v1 riportata sul v2: una sola camera di
profondità con più MODALITA' di visualizzazione, tutte con la curva gamma:

    Modo 1 -> grigio con gamma        (come kinect2_profondita2.py)
    Modo 2 -> TURBO con gamma         (come kinect2_profondita_turbo2.py)

Per aggiungere una modalità: scrivi una funzione render_xxx(depth) qui sotto
e aggiungila al dizionario MODALITA (le frecce e i tasti si adattano da soli).

Comandi (overlay del v1, con in più le frecce delle modalità in basso a destra):
  a tocco      -> foto / REC / pausa a destra, levetta gamma a sinistra,
                  frecce < > in basso a destra per la modalità, X per uscire
  pulsanti     -> rosso REC/stop, verde pausa, levetta premuta foto,
                  giallo esci, levetta su/giu gamma,
                  BIANCO / NERO = modalità precedente / successiva
  tastiera     -> 1 / 2 modalità, + / - gamma, Esc esci
Salva in ~/Desktop/ki_la_visto/registrazioni/Kinect v2/ (video e foto).
"""
import cv2

import kinect2_comune as k
from overlay_kinect2 import ControlliOverlayV2

stato = {"gamma": k.GAMMA_INIZIALE, "modalita": 1}


def render_grigio(depth):
    return k.profondita_gamma(depth, stato["gamma"])


def render_turbo(depth):
    return k.profondita_gamma_a_colori(depth, stato["gamma"], cv2.COLORMAP_TURBO)


MODALITA = {
    1: render_grigio,
    2: render_turbo,
}
NOMI_MODALITA = {1: "GRIGIO", 2: "TURBO"}  # mostrati nell'overlay accanto al numero

controlli = ControlliOverlayV2(larghezza=512, altezza=424,
                               con_gamma=True, stato_gamma=stato,
                               gamma_min=k.GAMMA_MIN, gamma_max=k.GAMMA_MAX,
                               con_modo=True, stato_modo=stato,
                               modo_min=min(MODALITA), modo_max=max(MODALITA),
                               nomi_modo=NOMI_MODALITA)

k.esegui_camera("Kinect 2 - K", colore=False, profondita=True,
                elabora=lambda f: MODALITA[stato["modalita"]](f["depth"]),
                overlay=controlli)
