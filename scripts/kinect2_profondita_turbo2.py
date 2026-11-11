#!/usr/bin/env python3
"""
Kinect Camera 2 - PROFONDITA' TURBO 2: curva GAMMA + colori TURBO (come il
modo 5 di camera_avanzata del Kinect v1) + overlay completo: REC, pausa,
foto, levetta gamma, X.

Comandi:
  a tocco      -> icone a destra (foto / REC / pausa), levetta gamma a
                  sinistra da trascinare, X in alto a destra
  pulsanti     -> rosso REC/stop, verde pausa, levetta premuta foto,
                  giallo esci, levetta su/giu gamma (come nel v1)
  tastiera     -> + / - gamma, Esc esci
Salva in ~/Desktop/ki_la_visto/registrazioni/Kinect v2/ (video e foto).
"""
import kinect2_comune as k
from overlay_kinect2 import ControlliOverlayV2

stato = {"gamma": k.GAMMA_INIZIALE}

controlli = ControlliOverlayV2(larghezza=512, altezza=424,
                               con_gamma=True, stato_gamma=stato,
                               gamma_min=k.GAMMA_MIN, gamma_max=k.GAMMA_MAX)

k.esegui_camera("Kinect 2 - Profondita Turbo 2", colore=False, profondita=True,
                elabora=lambda f: k.profondita_gamma_a_colori(f["depth"], stato["gamma"]),
                overlay=controlli)
