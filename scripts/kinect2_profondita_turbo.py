#!/usr/bin/env python3
"""Kinect Camera 2 - PROFONDITA' a colori (mappa TURBO). Esci: X, giallo o Esc."""
import kinect2_comune as k

k.esegui_camera("Kinect 2 - Profondita Turbo", colore=False, profondita=True,
                elabora=lambda f: k.profondita_a_colori(f["depth"]))
