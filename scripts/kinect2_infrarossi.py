#!/usr/bin/env python3
"""Kinect Camera 2 - camera INFRAROSSI (vede anche al buio). Esci: X, giallo o Esc."""
import kinect2_comune as k

k.esegui_camera("Kinect 2 - Infrarossi", colore=False, profondita=True,
                elabora=lambda f: k.ir_in_grigio(f["ir"]))
