"""
palette_experience.py
-----------------------
Le schermate "PALETTE" della Kinect Camera 2: scegli due colori e la camera
di profondità sfuma dal primo (ciò che è VICINO) al secondo (ciò che è
LONTANO). La camera vera è kinect2_palette.py; qui c'è solo la scelta.

Sfondo comune alle due schermate:
    [<-]  [ o PALETTE EXPERIENCE            ]  (orologio)  [X]
    +---------------------+   +---------------------+
    |  display 1: VICINO  |   |  display 2: LONTANO |    <- spenti finché
    +---------------------+   +---------------------+       non scegli
  <-        indietro: dalla ruota alla griglia, dalla griglia al menu
  PALETTE EXPERIENCE  parte la camera; premibile solo con due colori scelti
                      (spia verde accesa), altrimenti resta "abbassato"
  orologio  cronologia: a ogni pressione carica la coppia di colori usata
            la volta prima, poi quella ancora prima... fino alla più vecchia
  X         chiude il programma

Schermata 1 (griglia): 7 x 5 caselle sopra i due display. 33 colori, più
  in basso a sinistra la casella X (cancella l'ultima scelta: prima il
  colore 2, poi l'1) e in basso a destra il cerchio colorato che apre la ruota.
Schermata 2 (ruota): la ruota dei colori al centro (tocca e rilascia per
  scegliere) e la stessa casella X in basso a sinistra.

Regole: il primo colore scelto accende il display di sinistra, il secondo
quello di destra; il secondo non può essere uguale al primo; con due colori
scelti, per cambiarne uno va prima cancellato. I colori scelti restano
anche tornando al menu o chiudendo il programma.

Dove finiscono i dati (scelta attuale e cronologia completa):
    ~/.config/kinect_camera2/palette.json
"""

import colorsys
import glob
import hashlib
import json
import math
import os
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

import cv2
import numpy as np

from stile2000 import SS, COLORI, TESTO_INCISO, TESTO_LUCE, TESTO_SPENTO, Tela, bgr, immagine_tk

FILE_DATI = os.path.expanduser("~/.config/kinect_camera2/palette.json")
# Le immagini delle schermate costano qualche secondo di calcolo sul Pi: le
# calcoliamo una volta e le teniamo qui. Si rifanno da sole se cambiano lo
# schermo, i colori della griglia o il codice del disegno.
CARTELLA_CACHE = os.path.expanduser("~/.cache/kinect_camera2")

# 7 x 5 caselle, riga per riga. "CANCELLA" e "RUOTA" sono le due caselle
# speciali; tutto il resto sono colori (33 in tutto). Cambiali liberamente.
GRIGLIA = [
    ["#ffffff", "#c0c0c0", "#808080", "#404040", "#000000", "#8b4513", "#f5deb3"],  # bianchi, grigi, nero, terre
    ["#ff0000", "#ff8000", "#ffff00", "#00d000", "#00ffff", "#0040ff", "#8000ff"],  # colori pieni
    ["#ff80c0", "#ffb380", "#ffff99", "#99ffb3", "#99e6ff", "#99b3ff", "#cc99ff"],  # pastello
    ["#800020", "#b34700", "#808000", "#006633", "#008080", "#000080", "#660066"],  # scuri
    ["CANCELLA", "#ff00ff", "#ff0080", "#00cca3", "#ffd700", "#00a0ff", "RUOTA"],
]
RIGHE, COLONNE = len(GRIGLIA), len(GRIGLIA[0])

SCHERMO_SPENTO = np.array([0.150, 0.165, 0.155], np.float32)  # grigio-verde da TV spenta (BGR)
LED_ACCESO, LED_SPENTO = "#3fe05c", "#243028"
ROSSO_X = "#b3261e"


# =====================================================================
# Dati su disco: scelta attuale + cronologia
# =====================================================================
def carica_dati():
    try:
        with open(FILE_DATI) as f:
            d = json.load(f)
    except Exception:
        d = {}
    scelta = d.get("selezione") or [None, None]
    scelta = [(c.lower() if isinstance(c, str) else None) for c in (list(scelta) + [None, None])[:2]]
    if scelta[0] is None:
        scelta[1] = None
    cronologia = [e for e in d.get("cronologia", [])
                  if isinstance(e, dict) and e.get("vicino") and e.get("lontano")]
    return scelta, cronologia


def salva_dati(scelta, cronologia):
    try:
        os.makedirs(os.path.dirname(FILE_DATI), exist_ok=True)
        provvisorio = FILE_DATI + ".tmp"
        with open(provvisorio, "w") as f:
            json.dump({"selezione": scelta, "cronologia": cronologia}, f, indent=1)
        os.replace(provvisorio, FILE_DATI)  # scrittura "tutto o niente"
    except Exception as ex:
        print(f"[PALETTE] Non riesco a salvare {FILE_DATI}: {ex}", flush=True)


# =====================================================================
class PaletteExperience:
    def __init__(self, root, W, H, al_menu, chiudi_app, avvia_experience):
        """al_menu(): torna al menu principale. chiudi_app(): chiude tutto.
        avvia_experience(colore_vicino, colore_lontano): lancia la camera."""
        self.root, self.W, self.H = root, W, H
        self._al_menu, self._chiudi_app, self._avvia = al_menu, chiudi_app, avvia_experience
        self.colori, self.cronologia = carica_dati()
        self.indice_cronologia = -1     # -1 = non sto sfogliando la cronologia
        self.schermata = "griglia"
        self.premuto = None
        self.visibile = False
        self._pronta = False
        self._lucchetto = threading.Lock()
        self._geometria()

        self.canvas = tk.Canvas(root, width=W, height=H, highlightthickness=0, bd=0, cursor="hand2")
        self.id_immagine = self.canvas.create_image(0, 0, anchor="nw")
        self._scritte()
        self.canvas.bind("<ButtonPress-1>", self._tocco_giu)
        self.canvas.bind("<B1-Motion>", self._tocco_muovi)
        self.canvas.bind("<ButtonRelease-1>", self._tocco_su)

    # --- misure -----------------------------------------------------------
    def _geometria(self):
        W, H = self.W, self.H
        u = self.u = min(H, W * 0.6)
        m = 0.03 * u
        alt = 0.115 * u
        y0, y1 = m, m + alt
        self.r_indietro = (m, y0, m + 0.15 * u, y1)
        self.r_chiudi = (W - m - alt, y0, W - m, y1)
        self.c_cronologia = (W - m - alt - 0.03 * u - alt / 2, (y0 + y1) / 2, alt / 2)
        self.r_experience = (self.r_indietro[2] + 0.03 * u, y0,
                             self.c_cronologia[0] - alt / 2 - 0.03 * u, y1)
        ya, yb = y1 + 0.03 * u, H - m       # zona principale
        self.zona = (m, ya, W - m, yb)
        dx, dy, meta = 0.085 * u, 0.012 * u, 0.018 * u
        self.r_display = [(dx, ya + dy, W / 2 - meta, yb - dy),
                          (W / 2 + meta, ya + dy, W - dx, yb - dy)]
        # caselle
        cw, ch = (W - 2 * m) / COLONNE, (yb - ya) / RIGHE
        g = 0.011 * u
        self.celle = {(r, c): (m + c * cw + g, ya + r * ch + g, m + (c + 1) * cw - g, ya + (r + 1) * ch - g)
                      for r in range(RIGHE) for c in range(COLONNE)}
        self.cella_cancella = next(k for k in self.celle if GRIGLIA[k[0]][k[1]] == "CANCELLA")
        self.cella_ruota = next(k for k in self.celle if GRIGLIA[k[0]][k[1]] == "RUOTA")
        # ruota dei colori
        self.c_ruota = (W / 2, (ya + yb) / 2, min((yb - ya) / 2 - 0.03 * u, 0.37 * u))

    # --- disegno (parte pesante, solo numpy/OpenCV: può girare in un thread) --
    def prepara(self):
        with self._lucchetto:
            if self._pronta:
                return
            t0 = time.time()
            self._prepara_schermi()
            if self._carica_cache():
                self._pronta = True
                print(f"[PALETTE] Schermate caricate in {time.time() - t0:.2f}s", flush=True)
                return
            tela = Tela(self.W, self.H)
            u = self.u
            sfondo = tela.sfondo()
            for r in self.r_display:  # cornici incassate dei due display
                b = 0.016 * u
                tela.tasto(sfondo, tela.rett(r[0] - b, r[1] - b, r[2] + b, r[3] + b, raggio=0.034 * u),
                           COLORI["incavo_alto"] * 0.55, COLORI["incavo_basso"] * 0.7, stile="incavo")
            self.fondo = tela.riduci(sfondo)
            for i in (0, 1):
                self._schermo(self.fondo, i, None)

            # tasti della barra: un "pezzo" di immagine per ogni stato
            alt_striscia = int(round(self.r_indietro[3] + 0.09 * u)) * SS
            striscia = sfondo[:alt_striscia]
            self.pezzi = {}
            for nome, rett in (("indietro", self.r_indietro), ("chiudi", self.r_chiudi),
                               ("experience", self.r_experience),
                               ("cronologia", self._rett_cronologia())):
                for stile in ("rilievo", "premuto"):
                    s = striscia.copy()
                    self._tasto_barra(tela, s, nome, stile)
                    piccola = tela.riduci(s)
                    p = int(0.045 * u)
                    x0, y0 = max(0, int(rett[0]) - p), max(0, int(rett[1]) - p)
                    # sotto non oltre l'inizio della zona delle caselle, per non coprirle
                    x1, y1 = min(self.W, int(rett[2]) + p), min(int(self.zona[1]), int(rett[3]) + p)
                    self.pezzi[(nome, stile)] = (x0, y0, piccola[y0:y1, x0:x1].copy())
            del sfondo, striscia

            self.strato_griglia = self._strato(tela, self._disegna_griglia)
            self.strato_ruota = self._strato(tela, self._disegna_ruota)
            self._pronta = True
            print(f"[PALETTE] Schermate disegnate in {time.time() - t0:.1f}s", flush=True)
            self._salva_cache()

    # --- cache su disco delle immagini ------------------------------------
    def _file_cache(self):
        impronta = hashlib.sha1()
        qui = os.path.dirname(os.path.abspath(__file__))
        for nome in ("palette_experience.py", "stile2000.py"):
            try:
                with open(os.path.join(qui, nome), "rb") as f:
                    impronta.update(f.read())
            except OSError:
                pass
        return os.path.join(CARTELLA_CACHE, f"palette_{self.W}x{self.H}_{impronta.hexdigest()[:12]}.npz")

    def _carica_cache(self):
        try:
            d = np.load(self._file_cache())
            self.fondo = d["fondo"]
            self.strato_griglia = (d["griglia_colore"].astype(np.float32), d["griglia_trasp"].astype(np.float32) / 255)
            self.strato_ruota = (d["ruota_colore"].astype(np.float32), d["ruota_trasp"].astype(np.float32) / 255)
            self.pezzi = {}
            for chiave in d.files:
                if chiave.startswith("pezzo|"):
                    _, nome, stile, x0, y0 = chiave.split("|")
                    self.pezzi[(nome, stile)] = (int(x0), int(y0), d[chiave])
            return len(self.pezzi) == 8 and self.fondo.shape[:2] == (self.H, self.W)
        except Exception:
            return False

    def _salva_cache(self):
        try:
            os.makedirs(CARTELLA_CACHE, exist_ok=True)
            for vecchio in glob.glob(os.path.join(CARTELLA_CACHE, f"palette_{self.W}x{self.H}_*.npz")):
                os.remove(vecchio)
            dati = {"fondo": self.fondo,
                    "griglia_colore": np.round(self.strato_griglia[0]).astype(np.uint8),
                    "griglia_trasp": np.round(self.strato_griglia[1] * 255).astype(np.uint8),
                    "ruota_colore": np.round(self.strato_ruota[0]).astype(np.uint8),
                    "ruota_trasp": np.round(self.strato_ruota[1] * 255).astype(np.uint8)}
            for (nome, stile), (x0, y0, pezzo) in self.pezzi.items():
                dati[f"pezzo|{nome}|{stile}|{x0}|{y0}"] = pezzo
            np.savez(self._file_cache(), **dati)
        except Exception as ex:
            print(f"[PALETTE] Cache non salvata: {ex}", flush=True)

    def _rett_cronologia(self):
        cx, cy, r = self.c_cronologia
        return (cx - r, cy - r, cx + r, cy + r)

    def _tasto_barra(self, tela, img, nome, stile):
        u = self.u
        sp = 1.2 if stile == "premuto" else 0.0
        spess = 0.013 * u
        alto, basso = COLORI["tasto_alto"], COLORI["tasto_basso"]
        if nome == "cronologia":
            cx, cy, r = self.c_cronologia
            tela.tasto(img, tela.cerchio(cx, cy, r), alto, basso, stile=stile)
            tela.cerchio_inciso(img, cx, cy, r * 0.56, spess * 0.85, sposta=sp)
            tela.linea_incisa(img, [(cx, cy - r * 0.36), (cx, cy), (cx + r * 0.27, cy)], spess * 0.85, sposta=sp)
            return
        x0, y0, x1, y1 = {"indietro": self.r_indietro, "chiudi": self.r_chiudi,
                          "experience": self.r_experience}[nome]
        tela.tasto(img, tela.rett(x0, y0, x1, y1, raggio=0.022 * u), alto, basso, stile=stile)
        cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
        if nome == "indietro":
            xa, xb, f = cx + w * 0.24, cx - w * 0.24, h * 0.2
            tela.linea_incisa(img, [(xa, cy), (xb, cy)], spess, sposta=sp)
            tela.linea_incisa(img, [(xb + f, cy - f), (xb, cy), (xb + f, cy + f)], spess, sposta=sp)
        elif nome == "chiudi":
            d = h * 0.24
            tela.linea_incisa(img, [(cx - d, cy - d), (cx + d, cy + d)], spess * 1.1, sposta=sp)
            tela.linea_incisa(img, [(cx - d, cy + d), (cx + d, cy - d)], spess * 1.1, sposta=sp)

    def _strato(self, tela, disegna):
        """Disegna qualcosa come 'strato trasparente' da appoggiare sopra i
        display: lo disegniamo su fondo nero e su fondo bianco, e dalla
        differenza ricaviamo quanto è trasparente ogni punto (ombre comprese)."""
        h, w = self.H * SS, self.W * SS
        nero = np.zeros((h, w, 3), np.float32)
        bianco = np.ones((h, w, 3), np.float32)
        disegna(tela, nero)
        disegna(tela, bianco)
        n, b = tela.riduci_float(nero), tela.riduci_float(bianco)
        alfa = np.clip(1 - (b - n).mean(axis=2, keepdims=True), 0, 1)
        return (np.clip(n, 0, 1) * 255).astype(np.float32), (1 - alfa).astype(np.float32)

    def _casella_base(self, tela, img, cella):
        x0, y0, x1, y1 = self.celle[cella]
        tela.tasto(img, tela.rett(x0, y0, x1, y1, raggio=0.02 * self.u),
                   COLORI["tasto_alto"], COLORI["tasto_basso"])
        return x0, y0, x1, y1

    def _casella_cancella(self, tela, img):
        x0, y0, x1, y1 = self._casella_base(tela, img, self.cella_cancella)
        cx, cy, d = (x0 + x1) / 2, (y0 + y1) / 2, (y1 - y0) * 0.24
        s = 0.016 * self.u
        tela.linea_incisa(img, [(cx - d, cy - d), (cx + d, cy + d)], s, colore=ROSSO_X)
        tela.linea_incisa(img, [(cx - d, cy + d), (cx + d, cy - d)], s, colore=ROSSO_X)

    def _colori_ruota(self, cx, cy, R):
        """Riempimento 'ruota dei colori': la tinta gira con l'angolo, al
        centro è bianco e verso il bordo il colore si fa pieno."""
        def fn(x0, y0, w, h):
            ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
            dx, dy = (xs + x0) / SS - cx, (ys + y0) / SS - cy
            tinta = np.degrees(np.arctan2(-dy, dx)) % 360
            sat = np.clip(np.hypot(dx, dy) / R, 0, 1)
            hsv = np.dstack([tinta, sat, np.ones_like(sat)]).astype(np.float32)
            return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        return fn

    def _disegna_griglia(self, tela, img):
        u = self.u
        for (r, c), _ in self.celle.items():
            voce = GRIGLIA[r][c]
            if voce == "CANCELLA":
                self._casella_cancella(tela, img)
            elif voce == "RUOTA":
                x0, y0, x1, y1 = self._casella_base(tela, img, (r, c))
                cx, cy, R = (x0 + x1) / 2, (y0 + y1) / 2, (y1 - y0) * 0.36
                tela.tasto(img, tela.cerchio(cx, cy, R), colore_fn=self._colori_ruota(cx, cy, R),
                           stile="incavo", lucido=False)
            else:
                x0, y0, x1, y1 = self._casella_base(tela, img, (r, c))
                b = 0.013 * u
                col = bgr(voce)
                tela.tasto(img, tela.rett(x0 + b, y0 + b, x1 - b, y1 - b, raggio=0.011 * u),
                           col, col * 0.9, stile="incavo", lucido=False)

    def _disegna_ruota(self, tela, img):
        cx, cy, R = self.c_ruota
        tela.tasto(img, tela.cerchio(cx, cy, R + 0.024 * self.u), COLORI["tasto_alto"], COLORI["tasto_basso"])
        tela.tasto(img, tela.cerchio(cx, cy, R), colore_fn=self._colori_ruota(cx, cy, R),
                   stile="incavo", lucido=False)
        self._casella_cancella(tela, img)

    # --- i due display ------------------------------------------------------
    def _prepara_schermi(self):
        """Per ogni display: forma (angoli arrotondati), ombreggiatura da
        tubo catodico (bordi più scuri + righine) e riflesso del vetro."""
        self._schermi = []
        for r in self.r_display:
            x0, y0, x1, y1 = (int(round(v)) for v in r)
            w, h = x1 - x0, y1 - y0
            k = 4
            grande = np.zeros((h * k, w * k), np.uint8)
            rg = int(0.024 * self.u * k)
            cv2.rectangle(grande, (rg, 0), (w * k - rg, h * k), 255, -1)
            cv2.rectangle(grande, (0, rg), (w * k, h * k - rg), 255, -1)
            for cx, cy in ((rg, rg), (w * k - rg, rg), (rg, h * k - rg), (w * k - rg, h * k - rg)):
                cv2.circle(grande, (cx, cy), rg, 255, -1)
            alfa = cv2.resize(grande, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255
            ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
            xn, yn = xs / w, ys / h
            vignetta = 1 - 0.34 * ((xn - 0.5) ** 2 + (yn - 0.5) ** 2) * 2
            righine = 1 - 0.07 * (np.arange(h) % 2)[:, None]
            ombra = (vignetta * righine).astype(np.float32)[..., None]
            riflesso = (0.11 * np.clip(1 - (xn * 0.9 + yn * 1.5), 0, 1) ** 1.5).astype(np.float32)[..., None]
            self._schermi.append((x0, y0, x1, y1, alfa, ombra, riflesso))

    def _schermo(self, img, i, colore):
        """Colora il display i (0 = vicino, 1 = lontano). colore None = spento."""
        x0, y0, x1, y1, alfa, ombra, riflesso = self._schermi[i]
        zona = img[y0:y1, x0:x1].astype(np.float32)
        if colore is None:
            luce = (SCHERMO_SPENTO * ombra * 0.9 + riflesso * 0.5) * 255
        else:
            luce = (bgr(colore) * ombra * 0.95 + 0.02 + riflesso) * 255
        img[y0:y1, x0:x1] = np.clip(zona * (1 - alfa) + luce * alfa, 0, 255).astype(np.uint8)

    # --- composizione dell'immagine da mostrare -------------------------------
    def _componi(self):
        img = self.fondo.copy()
        for i, c in enumerate(self.colori):
            if c:
                self._schermo(img, i, c)
        premult, trasparenza = self.strato_griglia if self.schermata == "griglia" else self.strato_ruota
        f = img.astype(np.float32) * trasparenza + premult
        p = self.premuto
        cella = None
        if p and p[0] == "colore":
            cella = (p[1], p[2])
        elif p and p[0] == "cancella":
            cella = self.cella_cancella
        elif p and p[0] == "ruota":
            cella = self.cella_ruota
        if cella is not None:  # casella premuta: si scurisce un po'
            x0, y0, x1, y1 = (int(round(v)) for v in self.celle[cella])
            f[y0:y1, x0:x1] *= 0.78
        img = np.clip(f, 0, 255).astype(np.uint8)

        def stile(nome):
            return "premuto" if (p and p[0] == nome) else "rilievo"
        stili = {"indietro": stile("indietro"), "chiudi": stile("chiudi"), "cronologia": stile("cronologia"),
                 # non premibile = resta "abbassato"
                 "experience": "rilievo" if (self.pronta_a_partire() and stile("experience") == "rilievo") else "premuto"}
        for nome, st in stili.items():
            x0, y0, pezzo = self.pezzi[(nome, st)]
            img[y0:y0 + pezzo.shape[0], x0:x0 + pezzo.shape[1]] = pezzo
        return img

    def _aggiorna(self):
        if not self.visibile:
            return
        self._foto = immagine_tk(self._componi())
        self.canvas.itemconfig(self.id_immagine, image=self._foto)
        pronta = self.pronta_a_partire()
        giu = 1 if (not pronta or (self.premuto and self.premuto[0] == "experience")) else 0
        x, y = self._pos_testo
        self.canvas.coords(self.id_testo_luce, x + 1 + giu, y + 1 + giu)
        self.canvas.coords(self.id_testo, x + giu, y + giu)
        self.canvas.itemconfig(self.id_testo, fill=TESTO_INCISO if pronta else TESTO_SPENTO)
        self.canvas.itemconfig(self.id_led, fill=LED_ACCESO if pronta else LED_SPENTO)

    def _scritte(self):
        u = self.u
        x0, y0, x1, y1 = self.r_experience
        px = int(0.052 * u)
        while True:  # la scritta deve stare nel tasto, su qualunque schermo
            font = tkfont.Font(family="DejaVu Sans", size=-px, weight="bold")
            if font.measure("PALETTE EXPERIENCE") <= (x1 - x0) * 0.74 or px <= 10:
                break
            px -= 1
        self._pos_testo = ((x0 + x1) / 2 + 0.02 * u, (y0 + y1) / 2)
        x, y = self._pos_testo
        self.id_testo_luce = self.canvas.create_text(x + 1, y + 1, text="PALETTE EXPERIENCE", font=font, fill=TESTO_LUCE)
        self.id_testo = self.canvas.create_text(x, y, text="PALETTE EXPERIENCE", font=font, fill=TESTO_SPENTO)
        rl = 0.014 * u  # spia: verde quando si può partire
        lx = x0 + 0.045 * u
        self.id_led = self.canvas.create_oval(lx - rl, y - rl, lx + rl, y + rl, fill=LED_SPENTO, outline="#1a1c1e")
        rm = 0.03 * u   # mirino che segue il dito sulla ruota
        self._raggio_mirino = rm
        self.id_mirino = self.canvas.create_oval(0, 0, 2 * rm, 2 * rm, outline="#ffffff", width=3, state="hidden")
        self.id_mirino2 = self.canvas.create_oval(0, 0, 2 * rm, 2 * rm, outline="#1a1c1e", width=1, state="hidden")

    # --- mostra / nascondi ------------------------------------------------------
    def mostra(self):
        self.prepara()
        self.schermata = "griglia"
        self.indice_cronologia = -1
        self.premuto = None
        self.visibile = True
        self.canvas.pack(fill="both", expand=True)
        self._aggiorna()

    def nascondi(self):
        self.visibile = False
        self.canvas.pack_forget()

    # --- logica -----------------------------------------------------------
    def pronta_a_partire(self):
        return bool(self.colori[0] and self.colori[1])

    def scegli(self, colore):
        """Un colore toccato (casella o ruota). Ritorna True se è stato preso."""
        colore = colore.lower()
        if self.colori[0] is None:
            self.colori[0] = colore
        elif self.colori[1] is None:
            if colore == self.colori[0]:
                return False       # il secondo non può essere uguale al primo
            self.colori[1] = colore
        else:
            return False           # già due colori: prima va cancellato
        self.indice_cronologia = -1
        salva_dati(self.colori, self.cronologia)
        return True

    def cancella(self):
        """Toglie l'ultima scelta: prima il colore 2 (lontano), poi l'1."""
        if self.colori[1] is not None:
            self.colori[1] = None
        elif self.colori[0] is not None:
            self.colori[0] = None
        else:
            return False
        self.indice_cronologia = -1
        salva_dati(self.colori, self.cronologia)
        return True

    def cronologia_indietro(self):
        """Carica la coppia usata la volta prima; a ogni chiamata va più
        indietro. Arrivata alla più vecchia, non cambia più nulla."""
        if self.indice_cronologia + 1 >= len(self.cronologia):
            return False
        self.indice_cronologia += 1
        voce = self.cronologia[len(self.cronologia) - 1 - self.indice_cronologia]
        self.colori = [voce["vicino"].lower(), voce["lontano"].lower()]
        salva_dati(self.colori, self.cronologia)
        return True

    def parti(self):
        if not self.pronta_a_partire():
            return False
        vicino, lontano = self.colori
        ultima = self.cronologia[-1] if self.cronologia else None
        if not ultima or (ultima["vicino"].lower(), ultima["lontano"].lower()) != (vicino, lontano):
            self.cronologia.append({"vicino": vicino, "lontano": lontano,
                                    "quando": time.strftime("%Y-%m-%d %H:%M:%S")})
        self.indice_cronologia = -1
        salva_dati(self.colori, self.cronologia)
        print(f"[PALETTE] Experience: vicino {vicino} -> lontano {lontano}", flush=True)
        self._avvia(vicino, lontano)
        return True

    def indietro(self):
        if self.schermata == "ruota":
            self.schermata = "griglia"
            self._aggiorna()
        else:
            self.nascondi()
            self._al_menu()

    # --- tocco ------------------------------------------------------------
    def _colore_ruota_in(self, x, y):
        cx, cy, R = self.c_ruota
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d > R:
            return None
        tinta = (math.degrees(math.atan2(-dy, dx)) % 360) / 360
        r, g, b = colorsys.hsv_to_rgb(tinta, min(1.0, d / R), 1.0)
        return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))

    def bersaglio(self, x, y):
        def dentro(r, margine=0.0):
            return r[0] - margine <= x <= r[2] + margine and r[1] - margine <= y <= r[3] + margine
        bordo = 0.012 * self.u
        if dentro(self.r_indietro, bordo):
            return ("indietro",)
        if dentro(self.r_chiudi, bordo):
            return ("chiudi",)
        if dentro(self.r_experience):
            return ("experience",)
        cx, cy, r = self.c_cronologia
        if math.hypot(x - cx, y - cy) <= r * 1.15:
            return ("cronologia",)
        if dentro(self.celle[self.cella_cancella], bordo):
            return ("cancella",)
        if self.schermata == "ruota":
            colore = self._colore_ruota_in(x, y)
            return ("disco", colore) if colore else None
        for (r_, c_), rett in self.celle.items():
            if dentro(rett, bordo):
                voce = GRIGLIA[r_][c_]
                return ("ruota",) if voce == "RUOTA" else ("colore", r_, c_)
        return None

    def _mirino(self, x=None, y=None):
        if x is None:
            for i in (self.id_mirino, self.id_mirino2):
                self.canvas.itemconfig(i, state="hidden")
            return
        rm = self._raggio_mirino
        self.canvas.coords(self.id_mirino, x - rm, y - rm, x + rm, y + rm)
        self.canvas.coords(self.id_mirino2, x - rm - 2, y - rm - 2, x + rm + 2, y + rm + 2)
        for i in (self.id_mirino, self.id_mirino2):
            self.canvas.itemconfig(i, state="normal")

    def _tocco_giu(self, e):
        b = self.bersaglio(e.x, e.y)
        if b and b[0] == "experience" and not self.pronta_a_partire():
            b = None  # non premibile
        self.premuto = b
        if b and b[0] == "disco":
            self._mirino(e.x, e.y)
        elif b:
            self._aggiorna()

    def _tocco_muovi(self, e):
        if self.premuto and self.premuto[0] == "disco":
            if self._colore_ruota_in(e.x, e.y):
                self._mirino(e.x, e.y)
            else:
                self._mirino()

    def _tocco_su(self, e):
        premuto, self.premuto = self.premuto, None
        self._mirino()
        if premuto is None:
            return
        b = self.bersaglio(e.x, e.y)
        valido = b is not None and b[0] == premuto[0] and (b == premuto or b[0] == "disco")
        if valido:
            self.esegui(b)
        if self.visibile:
            self._aggiorna()

    def esegui(self, b):
        tipo = b[0]
        if tipo == "colore":
            self.scegli(GRIGLIA[b[1]][b[2]])
        elif tipo == "disco":
            self.scegli(b[1])      # il colore sotto il dito al momento del rilascio
        elif tipo == "cancella":
            self.cancella()
        elif tipo == "ruota":
            self.schermata = "ruota"
        elif tipo == "cronologia":
            self.cronologia_indietro()
        elif tipo == "experience":
            self.parti()
        elif tipo == "indietro":
            self.indietro()
        elif tipo == "chiudi":
            self._chiudi_app()
