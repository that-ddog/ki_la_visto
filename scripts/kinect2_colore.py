#!/usr/bin/env python3
"""Kinect Camera 2 - camera COLORE (1920x1080, mostrata ridotta). Esci: X, giallo o Esc."""
import kinect2_comune as k

k.esegui_camera("Kinect 2 - Colore", colore=True, profondita=False,
                elabora=lambda f: k.colore_in_bgr(f["color"]))
