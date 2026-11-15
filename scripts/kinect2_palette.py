#!/usr/bin/env python3
"""
kinect2_palette.py — la camera della "Palette Experience"
-----------------------------------------------------------
Camera di profondità che sfuma fra DUE colori scelti da te: il colore 1
per ciò che è più vicino, il colore 2 per ciò che è più lontano, e in mezzo
tutte le sfumature. Dove il Kinect non vede nulla resta nero.

La lancia la GUI (schermata PALETTE) passando i due colori:
    python3 kinect2_palette.py '#ff0000' '#0040ff'
Senza colori usa bianco -> nero (cioè la profondità in grigio).

Overlay e comandi come le altre camere di profondità: REC, pausa, foto,
levetta gamma in alto (qui decide dove cade il passaggio fra i due colori),
misuratore del microfono, X per uscire. Stessi pulsanti fisici.
Salva in ~/Desktop/ki_la_visto/registrazioni/Kinect v2/ (video e foto).
"""
import sys

import kinect2_comune as k
from overlay_kinect2 import ControlliOverlayV2

argomenti = [a for a in sys.argv[1:] if not a.startswith("--")]
try:
    VICINO = k.colore_da_esadecimale(argomenti[0]) if len(argomenti) > 0 else (255, 255, 255)
    LONTANO = k.colore_da_esadecimale(argomenti[1]) if len(argomenti) > 1 else (0, 0, 0)
except ValueError as ex:
    print(f"[PALETTE] {ex}: uso bianco -> nero", flush=True)
    VICINO, LONTANO = (255, 255, 255), (0, 0, 0)

print(f"[PALETTE] vicino (B,G,R)={VICINO}  lontano (B,G,R)={LONTANO}", flush=True)
TAVOLA = k.tavola_due_colori(VICINO, LONTANO)

stato = {"gamma": k.GAMMA_INIZIALE}

controlli = ControlliOverlayV2(larghezza=512, altezza=424,
                               con_gamma=True, stato_gamma=stato,
                               gamma_min=k.GAMMA_MIN, gamma_max=k.GAMMA_MAX)

k.esegui_camera("Kinect 2 - Palette Experience", colore=False, profondita=True,
                elabora=lambda f: k.profondita_due_colori(f["depth"], stato["gamma"], TAVOLA),
                overlay=controlli)
