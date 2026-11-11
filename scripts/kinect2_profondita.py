#!/usr/bin/env python3
"""Kinect Camera 2 - PROFONDITA' in grigio (vicino chiaro, lontano scuro). Esci: X, giallo o Esc."""
import kinect2_comune as k

k.esegui_camera("Kinect 2 - Profondita", colore=False, profondita=True,
                elabora=lambda f: k.profondita_in_grigio(f["depth"]))
