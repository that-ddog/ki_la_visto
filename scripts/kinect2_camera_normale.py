#!/usr/bin/env python3
"""
Kinect Camera 2 - CAMERA NORMALE: la telecamera a colori del Kinect v2
(1920x1080, mostrata e registrata a 640x360) + overlay: REC, pausa, foto, X.
Niente gamma, come la "video normale" del Kinect v1.

Comandi:
  a tocco      -> icone a destra (foto / REC / pausa), X in alto a destra
  pulsanti     -> rosso REC/stop, verde pausa, levetta premuta foto,
                  giallo esci (come nel v1)
  tastiera     -> Esc esci
Salva in ~/Desktop/ki_la_visto/registrazioni/Kinect v2/ (video e foto).
"""
import kinect2_comune as k
from overlay_kinect2 import ControlliOverlayV2

# 640x360: stessa scala dell'overlay delle altre camere sul piccolo
# schermo (icone comode da toccare). Il Kinect manda 1920x1080: se un
# giorno vuoi video più definiti, alza questi due numeri (sempre 16:9).
LARGHEZZA, ALTEZZA = 1920, 1080

controlli = ControlliOverlayV2(larghezza=LARGHEZZA, altezza=ALTEZZA, con_gamma=False)

k.esegui_camera("Kinect 2 - Camera normale", colore=True, profondita=False,
                elabora=lambda f: k.colore_in_bgr(f["color"], LARGHEZZA),
                overlay=controlli)
