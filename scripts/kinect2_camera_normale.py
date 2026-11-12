#!/usr/bin/env python3
"""
Kinect Camera 2 - CAMERA NORMALE: la telecamera a colori del Kinect v2
+ overlay: REC, pausa, foto, X.
Video e foto in FULL HD (1920x1080, la massima del Kinect v2); a schermo
un'anteprima 800x450 (circa la misura dello schermo), così le icone
dell'overlay restano grandi e comode da toccare.
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

# Misura dei video e delle foto salvati: la piena risoluzione del Kinect v2.
REGISTRAZIONE = (1920, 1080)

# Misura dell'anteprima a schermo (e quindi dell'overlay): circa quella
# dello schermo (800 di larghezza). Le icone dell'overlay hanno una misura
# fissa in pixel: più piccola è l'anteprima, più grandi appaiono a schermo.
# Sempre 16:9.
ANTEPRIMA = (800, 450)

controlli = ControlliOverlayV2(larghezza=ANTEPRIMA[0], altezza=ANTEPRIMA[1], con_gamma=False,
                               misura_registrazione=REGISTRAZIONE)

k.esegui_camera("Kinect 2 - Camera normale", colore=True, profondita=False,
                elabora=lambda f: k.colore_in_bgr(f["color"], REGISTRAZIONE[0]),
                overlay=controlli)
