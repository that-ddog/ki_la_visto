#!/usr/bin/env python3
"""
Kinect Camera 2 - INFRAROSSI 2: la camera infrarossa del Kinect v2 (vede
anche al buio) + overlay completo: REC, pausa, foto, levetta, X.

Qui la levetta "gamma" fa da luminosità: su = più chiaro, giù = più scuro.
Parte esattamente come l'infrarossi di prima (kinect2_infrarossi.py).

Comandi:
  a tocco      -> icone a destra (foto / REC / pausa), levetta a sinistra
                  da trascinare, X in alto a destra
  pulsanti     -> rosso REC/stop, verde pausa, levetta premuta foto,
                  giallo esci, levetta su/giu luminosità (come nel v1)
  tastiera     -> + / - luminosità, Esc esci
Salva in ~/Desktop/ki_la_visto/registrazioni/Kinect v2/ (video e foto).
"""
import kinect2_comune as k
from overlay_kinect2 import ControlliOverlayV2

stato = {"gamma": k.IR_GAMMA_INIZIALE}

controlli = ControlliOverlayV2(larghezza=512, altezza=424,
                               con_gamma=True, stato_gamma=stato,
                               gamma_min=k.GAMMA_MIN, gamma_max=k.GAMMA_MAX)

k.esegui_camera("Kinect 2 - Infrarossi 2", colore=False, profondita=True,
                elabora=lambda f: k.ir_gamma(f["ir"], stato["gamma"]),
                overlay=controlli)
