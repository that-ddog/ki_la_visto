#!/usr/bin/env python3
r"""
gui_kinect2.py
----------------
GUI principale della "Kinect Camera 2", stile pulsantiera di una videocamera
anni 2000 (argento spazzolato, tasti in plastica in rilievo).

    (D)                                   [ 4.98V ] [X]

                 ___________________
               /  CAMERA | INFRAROSSI \
              |       ( K )            |
               \  MEDIA  | PALETTE    /
                 -------------------
    [logo graffiato]                          ( v2 )

  CAMERA      -> telecamera normale a colori        (kinect2_camera_normale.py)
  INFRAROSSI  -> camera a infrarossi                (kinect2_infrarossi2.py)
  K (centro)  -> camera di profondità con modalità  (kinect2_avanzata.py)
  MEDIA       -> apre la cartella con foto e video (la GUI resta aperta)
  PALETTE     -> per ora non fa nulla (si preme, ma niente azione)
  D           -> DOOM (doom_ponte.py, comandi fisici come nella Camera 1)
  X           -> chiude l'app

Comandi:
  - tocco / mouse su tutti i tasti
  - levetta: si muove SOLO fra i 5 tasti della ghiera. In orizzontale e
    verticale passa da uno spicchio all'altro; in DIAGONALE si va dallo
    spicchio al tasto K (e da K allo spicchio in quella direzione).
    Il VERDE preme il tasto evidenziato. D e X solo a tocco.

Come è disegnata: l'intero pannello è un'immagine calcolata con numpy/OpenCV
(sfondo spazzolato, rilievi, ombre, bagliore della selezione), una per ogni
stato (tasto evidenziato / premuto) e tenuta in memoria; le scritte sono
testo di Tk sopra l'immagine (così i caratteri sono nitidi).

La vecchia GUI a griglia è in gui_kinect2_griglia.py, come riserva.
"""

import base64
import math
import os
import shutil
import subprocess
import threading
import traceback
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

import cv2
import numpy as np

try:
    from overlay_rec import leggi_tensione_ingresso
except Exception:
    def leggi_tensione_ingresso():
        return None

CARTELLA_SCRIPT = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.expanduser("~/kinect-py311/bin/python3")
SCRIPT_MENU_INPUT_BRIDGE = os.path.join(CARTELLA_SCRIPT, "menu_input_bridge.py")
FILE_LOG = os.path.join(CARTELLA_SCRIPT, "kinect2_log.txt")
CARTELLA_MEDIA = os.path.expanduser("~/Desktop/ki_la_visto/registrazioni/Kinect v2")

SCRIPT_DOOM_PONTE = os.path.join(CARTELLA_SCRIPT, "doom_ponte.py")
COMANDO_DOOM = shutil.which("chocolate-doom") or "/usr/games/chocolate-doom"

# Cosa lancia ogni tasto della ghiera (None = nessuno script, azione speciale)
SCRIPT_TASTI = {
    "camera": "kinect2_camera_normale.py",
    "infrarossi": "kinect2_infrarossi2.py",
    "k": "kinect2_avanzata.py",
}

# Levetta: dove si va da ogni tasto della ghiera (vedi docstring).
NAVIGAZIONE = {
    "camera":     {"destra": "infrarossi", "giu": "media", "giu-destra": "k"},
    "infrarossi": {"sinistra": "camera", "giu": "palette", "giu-sinistra": "k"},
    "media":      {"su": "camera", "destra": "palette", "su-destra": "k"},
    "palette":    {"su": "infrarossi", "sinistra": "media", "su-sinistra": "k"},
    "k":          {"su-sinistra": "camera", "su-destra": "infrarossi",
                   "giu-sinistra": "media", "giu-destra": "palette"},
}

# =====================================================================
# Colori (BGR 0..1 per il disegno con OpenCV, #RRGGBB per i testi di Tk)
# =====================================================================
def _bgr(esadecimale):
    e = esadecimale.lstrip("#")
    r, g, b = int(e[0:2], 16), int(e[2:4], 16), int(e[4:6], 16)
    return np.array([b, g, r], np.float32) / 255.0


COLORI = {
    "sfondo_alto": _bgr("#dcdee1"),      # argento chiaro (in alto)
    "sfondo_basso": _bgr("#9ea3a9"),     # argento più scuro (in basso)
    "tasto_alto": _bgr("#f1f2f3"),       # plastica argentata dei tasti
    "tasto_basso": _bgr("#b4b9bf"),
    "incavo_alto": _bgr("#8d9298"),      # conca in cui sta la ghiera
    "incavo_basso": _bgr("#c3c7cc"),
    "grafite_alto": _bgr("#5a5d62"),     # tasto K, plastica grafite
    "grafite_basso": _bgr("#25272a"),
    "lcd_alto": _bgr("#a9b89f"),         # display LCD verdino anni 2000
    "lcd_basso": _bgr("#93a38a"),
    "selezione": _bgr("#4fc3f7"),        # bagliore azzurro del tasto evidenziato
}
TESTO_INCISO = "#3a3e44"        # scritte "incise" sulla plastica argentata
TESTO_LUCE = "#f7f8f9"          # riflesso chiaro sotto le scritte incise
TESTO_K = "#e9ebee"
TESTO_DOOM = "#c62828"
TESTO_LCD = "#1e281e"
TESTO_LCD_SPENTO = "#9aaa91"    # i segmenti "spenti" dell'LCD (88.88V in trasparenza)
TESTO_BADGE = "#1f4fb5"         # blu tipo "30x OPTICAL ZOOM"

SS = 2  # disegniamo a risoluzione doppia e poi rimpiccioliamo: bordi lisci

# =====================================================================
# Il logo dell'autore (dal disegno a matita), in tratti vettoriali:
# coordinate in millesimi dell'altezza del logo. Ricavato dalla foto con
# soglia + scheletro + semplificazione, così si disegna nitido a ogni misura.
# =====================================================================
LOGO_RAPPORTO = 1.0647   # larghezza / altezza
LOGO_PUNTI = [[930,416]]  # il puntino dell'occhio del pesce
LOGO_TRATTI = [
    [[73,939],[81,939],[81,952],[66,982],[55,979],[33,962],[28,955],[32,949],[72,939]],
    [[532,544],[535,543],[538,549],[542,585],[532,583],[513,567],[524,548],[531,545]],
    [[473,503],[479,505],[476,514],[464,536],[427,518],[422,510],[432,505],[472,503]],
    [[527,496],[531,496],[534,527],[536,530],[536,541],[524,548],[512,566],[464,537],[479,504],[490,498],[505,500],[526,496]],
    [[559,493],[567,492],[570,494],[568,503],[547,526],[536,529],[531,496],[543,493],[558,493]],
    [[516,448],[519,448],[522,451],[526,461],[529,494],[506,499],[498,477],[509,454],[516,448]],
    [[627,400],[638,402],[645,406],[736,490],[665,563],[640,586],[629,590],[626,589],[636,512],[635,455],[627,401]],
    [[942,385],[949,386],[960,396],[962,425],[955,436],[943,444],[919,444],[904,432],[901,417],[902,410],[909,396],[927,385],[941,385]],
    [[898,348],[904,348],[935,370],[943,383],[941,385],[923,387],[906,400],[901,417],[903,430],[910,438],[919,444],[938,446],[950,440],[962,425],[960,396],[972,400],[1040,448],[1050,458],[1051,466],[1048,474],[966,543],[890,617],[882,618],[819,567],[782,529],[738,490],[821,414],[851,383],[897,348]],
    [[899,347],[891,351],[851,383],[821,414],[737,490],[645,406],[628,400],[627,410],[635,455],[636,512],[626,577],[626,591],[640,586],[738,490],[782,529],[819,567],[880,617],[888,618],[900,609],[966,543],[1048,474],[1051,466],[1050,458],[1040,448],[972,400],[960,396],[942,382],[935,370],[908,351],[900,348]],
    [[689,132],[693,133],[690,174],[642,174],[637,171],[643,160],[678,134],[688,132]],
    [[143,123],[145,122],[150,126],[156,151],[181,218],[200,279],[202,291],[65,292],[63,290],[66,280],[76,268],[115,196],[138,128],[142,123]],
    [[308,80],[335,81],[343,84],[343,99],[369,176],[370,192],[354,193],[345,188],[343,177],[333,157],[320,115],[312,97],[308,81]],
    [[270,70],[269,70],[276,70],[300,75],[308,80],[312,97],[320,115],[332,153],[343,177],[344,189],[354,193],[372,191],[378,195],[418,196],[378,195],[371,191],[369,176],[343,99],[342,85],[357,84],[389,92],[357,84],[343,84],[321,79],[308,80],[300,75],[271,70]],
    [[524,13],[528,13],[525,28],[481,130],[476,134],[458,124],[447,121],[447,138],[451,152],[459,161],[467,155],[474,139],[477,137],[557,191],[577,202],[584,201],[623,175],[636,170],[642,174],[688,173],[690,189],[684,265],[673,348],[671,352],[656,348],[636,330],[577,269],[565,264],[558,269],[511,341],[504,346],[490,336],[464,305],[440,267],[432,262],[425,267],[406,350],[399,373],[391,414],[379,455],[366,519],[362,526],[360,540],[334,640],[302,739],[302,760],[278,809],[301,761],[312,756],[408,621],[413,608],[453,551],[459,538],[464,536],[492,554],[497,555],[510,566],[497,585],[494,593],[483,606],[479,618],[446,675],[432,711],[415,741],[351,831],[346,846],[406,839],[448,830],[497,830],[591,714],[639,664],[652,659],[654,668],[640,796],[640,837],[644,864],[651,881],[652,898],[541,893],[411,898],[235,914],[157,928],[94,931],[97,906],[126,813],[162,717],[185,643],[237,502],[250,451],[248,431],[208,310],[206,295],[312,289],[317,285],[288,202],[264,155],[223,92],[187,48],[185,36],[195,34],[221,37],[286,37],[343,28],[426,24],[462,18],[498,17],[523,13]],
    [[525,12],[498,17],[470,17],[426,24],[343,28],[286,37],[221,37],[195,34],[184,36],[187,48],[211,76],[250,132],[279,183],[300,231],[315,274],[316,284],[312,289],[208,294],[202,292],[181,218],[156,151],[150,126],[144,121],[138,128],[119,186],[110,206],[76,268],[66,280],[62,290],[67,293],[202,291],[206,294],[208,310],[224,355],[228,374],[248,431],[250,451],[237,502],[185,643],[162,717],[126,813],[97,906],[93,931],[83,938],[68,939],[32,949],[27,954],[33,962],[55,979],[67,982],[81,952],[81,939],[93,931],[157,928],[235,914],[411,898],[541,893],[653,898],[640,837],[640,796],[654,668],[652,658],[639,664],[591,714],[497,830],[448,830],[366,845],[347,845],[351,831],[415,741],[432,711],[446,675],[479,618],[483,606],[494,594],[497,585],[508,568],[512,566],[532,583],[542,586],[538,549],[535,543],[536,531],[547,526],[557,516],[571,495],[567,492],[530,495],[526,461],[522,451],[518,447],[509,454],[487,500],[479,505],[475,502],[426,506],[422,510],[427,518],[461,536],[442,568],[413,608],[408,621],[312,756],[301,758],[303,736],[334,640],[362,528],[366,519],[379,455],[391,414],[399,373],[406,350],[425,267],[432,262],[437,264],[464,305],[490,336],[504,346],[511,341],[558,269],[565,264],[577,269],[609,303],[656,348],[668,352],[673,348],[684,265],[692,166],[692,130],[678,134],[640,163],[636,171],[623,175],[581,202],[574,201],[557,191],[488,143],[480,140],[477,134],[482,128],[525,28],[529,13],[526,12]],
]


# =====================================================================
# Disegno del pannello
# =====================================================================
class Pannello:
    """Calcola la geometria e disegna il pannello per un dato stato
    (tasto evidenziato, tasto premuto). Le immagini vengono tenute in
    memoria: ogni stato si calcola una volta sola."""

    TASTI_GHIERA = ("camera", "infrarossi", "media", "palette", "k")

    def __init__(self, W, H):
        self.W, self.H = W, H
        u = self.u = min(H, W * 0.6)  # unità di misura: tutto scala con lo schermo
        self.cx, self.cy = W / 2, H * 0.52
        self.R_out = 0.40 * u
        self.R_in = 0.235 * u
        self.gap = 0.022 * u
        self.R_conca = self.R_out + 0.032 * u
        self.r_anello = self.R_in - self.gap          # anello cromato attorno alla K
        self.r_k = self.r_anello - 0.024 * u          # disco grafite della K
        m = self.margine = 0.045 * u
        self.r_d = 0.062 * u
        self.c_d = (m + self.r_d, m + self.r_d)
        lato_x = 0.12 * u
        self.rett_x = (W - m - lato_x, m, W - m, m + lato_x)
        lcd_w, lcd_h = 0.24 * u, 0.085 * u
        lcd_cy = m + lato_x / 2
        lcd_x1 = self.rett_x[0] - 0.035 * u
        self.rett_lcd = (lcd_x1 - lcd_w, lcd_cy - lcd_h / 2, lcd_x1, lcd_cy + lcd_h / 2)
        self.badge = (W - m - 0.15 * u, H - m - 0.06 * u, 0.145 * u, 0.05 * u)  # cx, cy, semiassi
        self.cache = {}
        self._varianti = {}
        self._lucchetto = threading.Lock()
        self.ferma_precalcolo = threading.Event()
        self._prepara_maschere()
        self._base = self._disegna_base()

    # --- maschere (a risoluzione SS) ----------------------------------
    def _griglia(self):
        h, w = self.H * SS, self.W * SS
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        return (xx + 0.5) / SS, (yy + 0.5) / SS

    @staticmethod
    def _ritaglia(maschera, margine):
        """Ritorna (maschera_ritagliata, x0, y0, bbox interna) con un margine
        attorno per ombre e bagliori: così i calcoli si fanno solo lì."""
        ys, xs = np.nonzero(maschera)
        h, w = maschera.shape
        y0, y1 = max(0, ys.min() - margine), min(h, ys.max() + margine + 1)
        x0, x1 = max(0, xs.min() - margine), min(w, xs.max() + margine + 1)
        interno = (ys.min() - y0, ys.max() - y0, xs.min() - x0, xs.max() - x0)
        return maschera[y0:y1, x0:x1], x0, y0, interno

    def _prepara_maschere(self):
        xx, yy = self._griglia()
        dx, dy = xx - self.cx, yy - self.cy
        r = np.hypot(dx, dy)
        g = self.gap / 2
        anello = (r <= self.R_out) & (r >= self.R_in)
        quadranti = {
            "camera": (dx < -g) & (dy < -g),
            "infrarossi": (dx > g) & (dy < -g),
            "media": (dx < -g) & (dy > g),
            "palette": (dx > g) & (dy > g),
        }
        margine = int(0.07 * self.u * SS)
        k_tondo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.035 * self.u * SS),) * 2)

        def finisci(booleana, arrotonda=False):
            m = booleana.astype(np.uint8) * 255
            if arrotonda:  # spigoli arrotondati, come una vera plastica stampata
                m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k_tondo)
            m = cv2.GaussianBlur(m, (0, 0), 0.8)
            return self._ritaglia(m, margine)

        self.maschere = {nome: finisci(anello & q, True) for nome, q in quadranti.items()}
        self.maschere["anello_k"] = finisci(r <= self.r_anello)
        corpi = np.zeros(xx.shape, np.float32)
        for nome in ("camera", "infrarossi", "media", "palette", "anello_k"):
            m8, x0, y0, _ = self.maschere[nome]
            zona = corpi[y0:y0 + m8.shape[0], x0:x0 + m8.shape[1]]
            np.maximum(zona, m8.astype(np.float32) / 255.0, out=zona)
        self._corpi_ghiera = corpi
        self.maschere["k"] = finisci(r <= self.r_k)
        self.maschere["conca"] = finisci(r <= self.R_conca)
        self.maschere["d"] = finisci(np.hypot(xx - self.c_d[0], yy - self.c_d[1]) <= self.r_d)

        x0, y0, x1, y1 = self.rett_x
        rx = np.zeros(xx.shape, np.uint8)
        cv2.rectangle(rx, (int(x0 * SS), int(y0 * SS)), (int(x1 * SS), int(y1 * SS)), 255, -1)
        self.maschere["x"] = finisci(rx > 0, True)

        x0, y0, x1, y1 = self.rett_lcd
        cornice = np.zeros(xx.shape, np.uint8)
        b = 0.012 * self.u
        cv2.rectangle(cornice, (int((x0 - b) * SS), int((y0 - b) * SS)),
                      (int((x1 + b) * SS), int((y1 + b) * SS)), 255, -1)
        self.maschere["lcd_cornice"] = finisci(cornice > 0, True)
        schermo = np.zeros(xx.shape, np.uint8)
        cv2.rectangle(schermo, (int(x0 * SS), int(y0 * SS)), (int(x1 * SS), int(y1 * SS)), 255, -1)
        self.maschere["lcd"] = finisci(schermo > 0)

        bx, by, ax, ay = self.badge
        badge = ((xx - bx) / ax) ** 2 + ((yy - by) / ay) ** 2 <= 1
        self.maschere["badge"] = finisci(badge)

    # --- primitive di disegno -------------------------------------------
    def _tasto(self, img, nome, alto=None, basso=None, stile="rilievo",
               colore_fn=None, lucido=True):
        """Disegna un tasto in plastica: ombra portata, corpo con sfumatura,
        smusso illuminato da in alto a sinistra. stile: 'rilievo' (normale),
        'premuto' (schiacciato) o 'incavo' (conca scavata nel pannello)."""
        m8, x0, y0, (by0, by1, bx0, bx1) = self.maschere[nome]
        h, w = m8.shape
        roi = img[y0:y0 + h, x0:x0 + w]
        mf = m8.astype(np.float32) / 255.0
        u = self.u * SS

        if stile in ("rilievo", "premuto"):
            spost = 0.012 * u if stile == "rilievo" else 0.004 * u
            forza = 0.32 if stile == "rilievo" else 0.16
            M = np.float32([[1, 0, spost * 0.4], [0, 1, spost]])
            ombra = cv2.GaussianBlur(cv2.warpAffine(mf, M, (w, h)), (0, 0), 0.014 * u)
            roi *= (1 - forza * ombra)[..., None]

        t = np.clip((np.arange(h, dtype=np.float32) - by0) / max(1, by1 - by0), 0, 1)[:, None, None]
        if colore_fn is not None:
            colore = colore_fn(x0, y0, w, h)
        else:
            colore = alto * (1 - t) + basso * t

        mb = cv2.GaussianBlur(mf, (0, 0), 0.007 * u)
        gx = cv2.Sobel(mb, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(mb, cv2.CV_32F, 0, 1, ksize=3)
        luce = gx * 0.45 + gy * 0.9
        luce /= (np.abs(luce).max() + 1e-6)
        if stile in ("premuto", "incavo"):
            luce = -luce
        chiaro = np.clip(luce, 0, 1)[..., None]
        scuro = np.clip(-luce, 0, 1)[..., None]
        colore = colore + (1 - colore) * chiaro * 0.6
        colore = colore * (1 - scuro * 0.45)

        if stile == "rilievo" and lucido:
            colore = colore + 0.05 * (1 - t) ** 2
        if stile == "premuto":
            colore = colore * 0.88
        a = mf[..., None]
        roi[:] = roi * (1 - a) + np.clip(colore, 0, 1) * a

    def _evidenzia(self, img, nome):
        """Bagliore azzurro attorno al tasto evidenziato + bordino interno.
        Fatto DOPO aver disegnato tutti i tasti, e solo negli spazi liberi
        (fessure e conca), così nessun tasto vicino lo copre o ne viene
        colorato."""
        m8, x0, y0, _ = self.maschere[nome]
        h, w = m8.shape
        roi = img[y0:y0 + h, x0:x0 + w]
        mf = m8.astype(np.float32) / 255.0
        u = self.u * SS
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.02 * u) | 1,) * 2)
        alone = np.clip(cv2.GaussianBlur(cv2.dilate(mf, k), (0, 0), 0.016 * u) * 1.7, 0, 1)
        liberi = 1 - self._corpi_ghiera[y0:y0 + h, x0:x0 + w]
        a = (alone * liberi * 0.9)[..., None]
        roi[:] = roi * (1 - a) + COLORI["selezione"] * a
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.008 * u) | 1,) * 2)
        bordo = (np.clip(mf - cv2.erode(mf, k), 0, 1) * 0.8)[..., None]
        roi[:] = roi * (1 - bordo) + COLORI["selezione"] * bordo

    def _cromato(self, centro):
        """Colore 'metallo cromato' con riflessi a fasce, per anello e badge."""
        def fn(x0, y0, w, h):
            ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
            phi = np.arctan2(ys + y0 - centro[1] * SS, xs + x0 - centro[0] * SS)
            v = 0.72 + 0.22 * np.cos(2 * (phi + math.pi / 4)) + 0.06 * np.cos(6 * phi)
            return (v[..., None] * np.array([0.98, 0.97, 0.95], np.float32)).astype(np.float32)
        return fn

    def _grafite(self, premuto):
        """Plastica grafite bombata per il tasto K, con riflesso in alto a sinistra."""
        def fn(x0, y0, w, h):
            ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
            X = (xs + x0) / SS - self.cx
            Y = (ys + y0) / SS - self.cy
            t = np.clip((Y + self.r_k) / (2 * self.r_k), 0, 1)[..., None]
            base = COLORI["grafite_alto"] * (1 - t) + COLORI["grafite_basso"] * t
            hx, hy = -0.32 * self.r_k, -0.42 * self.r_k
            spot = np.exp(-((X - hx) ** 2 + (Y - hy) ** 2) / (2 * (0.42 * self.r_k) ** 2))
            amp = 0.10 if premuto else 0.22
            return base + amp * spot[..., None]
        return fn

    # --- base (tutto ciò che non cambia mai) ----------------------------
    def _disegna_base(self):
        h, w = self.H * SS, self.W * SS
        t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        img = COLORI["sfondo_alto"] * (1 - t) + COLORI["sfondo_basso"] * t
        img = np.repeat(img, w, axis=1).astype(np.float32)

        # alluminio spazzolato: righe orizzontali sottili e irregolari
        rng = np.random.default_rng(2007)
        rumore = rng.standard_normal((h, w)).astype(np.float32)
        rumore = cv2.blur(rumore, (max(3, w // 5), 1))
        rumore = rumore / (rumore.std() + 1e-6) * 0.016
        img += rumore[..., None]

        # leggera vignettatura ai bordi
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        v = ((xs / w - 0.5) ** 2 + (ys / h - 0.5) ** 2)
        img *= (1 - 0.18 * v)[..., None]

        self._tasto(img, "conca", COLORI["incavo_alto"], COLORI["incavo_basso"], stile="incavo")
        self._tasto(img, "lcd_cornice", COLORI["incavo_alto"] * 0.7, COLORI["incavo_basso"] * 0.8,
                    stile="incavo")
        self._tasto(img, "lcd", COLORI["lcd_alto"], COLORI["lcd_basso"], stile="incavo")
        self._tasto(img, "badge", colore_fn=self._cromato((self.badge[0], self.badge[1])))
        self._graffia_logo(img)
        return img

    def _graffia_logo(self, img):
        """Il logo in basso a sinistra, come graffiato a mano con una punta
        sull'alluminio: solco scuro, bordo chiaro dove il metallo prende
        luce, profondità irregolare, mano che trema un po', e qualche
        micrograffio di 'vissuto' attorno."""
        u = self.u
        alto = 0.30 * u
        largo = alto * LOGO_RAPPORTO
        x0 = self.margine + 0.005 * u
        y0 = self.H - self.margine - alto + 0.01 * u
        # zona di lavoro (a risoluzione SS), con un po' di margine
        bx0, by0 = int((x0 - 0.04 * u) * SS), int((y0 - 0.04 * u) * SS)
        bx1, by1 = int((x0 + largo + 0.04 * u) * SS), int((y0 + alto + 0.04 * u) * SS)
        bx0, by0 = max(0, bx0), max(0, by0)
        bx1, by1 = min(img.shape[1], bx1), min(img.shape[0], by1)
        h, w = by1 - by0, bx1 - bx0
        rng = np.random.default_rng(1971)
        FIX = 16  # coordinate in sedicesimi di pixel (shift=4): tratti lisci

        def a_pixel(punti):
            xy = np.array(punti, np.float32) / 1000.0 * alto
            xy[:, 0] += x0
            xy[:, 1] += y0
            xy = xy * SS - np.array([bx0, by0], np.float32)
            xy += rng.normal(0, 0.3 * SS, xy.shape)  # la mano che trema
            return np.round(xy * FIX).astype(np.int32)

        solco = np.zeros((h, w), np.float32)
        spessore = max(1, int(round(0.0065 * u * SS)))
        for tratto in LOGO_TRATTI:
            cv2.polylines(solco, [a_pixel(tratto)], False, 1.0, spessore, cv2.LINE_AA, shift=4)
        for punto in LOGO_PUNTI:
            c = a_pixel([punto])[0]
            cv2.circle(solco, (int(c[0]), int(c[1])), int(0.0022 * u * SS * FIX), 1.0, -1,
                       cv2.LINE_AA, shift=4)

        # micrograffi: segmentini sottili e casuali, appena visibili
        micro = np.zeros((h, w), np.float32)
        for _ in range(26):
            cx, cy = rng.uniform(0.05, 0.95) * w, rng.uniform(0.05, 0.95) * h
            ang = rng.uniform(0, math.pi)
            lung = rng.uniform(0.015, 0.06) * u * SS
            p1 = (int((cx - math.cos(ang) * lung / 2) * FIX), int((cy - math.sin(ang) * lung / 2) * FIX))
            p2 = (int((cx + math.cos(ang) * lung / 2) * FIX), int((cy + math.sin(ang) * lung / 2) * FIX))
            cv2.line(micro, p1, p2, rng.uniform(0.15, 0.4), 1, cv2.LINE_AA, shift=4)

        # profondità irregolare lungo il tratto (+ qualche punto dove la
        # punta è "saltata" e il segno è più leggero)
        rumore = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 2.5 * SS)
        rumore = (rumore - rumore.min()) / (rumore.max() - rumore.min() + 1e-6)
        prof = solco * (0.45 + 0.55 * rumore) + micro

        spost = 0.9 * SS  # il bordo in luce è il lato in basso a destra del solco
        M = np.float32([[1, 0, spost], [0, 1, spost]])
        luce = np.clip(cv2.warpAffine(prof, M, (w, h)) - prof, 0, 1)
        zona = img[by0:by1, bx0:bx1]
        zona *= (1 - 0.5 * prof)[..., None]
        zona += (1 - zona) * (0.6 * luce)[..., None]

    # --- un'immagine completa per uno stato -----------------------------
    def _variante(self, premuto):
        """Il pannello completo, ad alta risoluzione, con il tasto 'premuto'
        schiacciato (None = nessuno). È la parte lenta: ce n'è una per tasto,
        calcolata una volta sola (anche in sottofondo, vedi precalcola)."""
        with self._lucchetto:
            if premuto in self._varianti:
                return self._varianti[premuto]
        img = self._base.copy()

        def stile(nome):
            return "premuto" if premuto == nome else "rilievo"

        for nome in ("camera", "infrarossi", "media", "palette"):
            self._tasto(img, nome, COLORI["tasto_alto"], COLORI["tasto_basso"], stile=stile(nome))
        self._tasto(img, "anello_k", colore_fn=self._cromato((self.cx, self.cy)),
                    stile=stile("k"), lucido=False)
        self._tasto(img, "k", colore_fn=self._grafite(premuto == "k"),
                    stile="premuto" if premuto == "k" else "rilievo", lucido=False)
        self._tasto(img, "d", COLORI["tasto_alto"], COLORI["tasto_basso"], stile=stile("d"))
        self._tasto(img, "x", COLORI["tasto_alto"], COLORI["tasto_basso"], stile=stile("x"))
        self._disegna_croce_x(img)
        variante = (np.clip(img, 0, 1) * 255).astype(np.uint8)  # in uint8: 4 volte meno memoria
        with self._lucchetto:
            self._varianti[premuto] = variante
        return variante

    def immagine(self, selezionato, premuto):
        """Immagine finale (a misura di schermo) per uno stato: parte dalla
        variante col tasto premuto e ci aggiunge solo il bagliore azzurro
        del tasto evidenziato, che è veloce."""
        chiave = (selezionato, premuto)
        with self._lucchetto:
            if chiave in self.cache:
                return self.cache[chiave]
        img = self._variante(premuto).astype(np.float32) / 255.0
        if selezionato:
            self._evidenzia(img, "anello_k" if selezionato == "k" else selezionato)
        finale = cv2.resize(np.clip(img, 0, 1), (self.W, self.H), interpolation=cv2.INTER_AREA)
        finale = (finale * 255).astype(np.uint8)
        with self._lucchetto:
            self.cache[chiave] = finale
        return finale

    def precalcola(self):
        """Da lanciare in un thread all'avvio: prepara tutte le varianti
        (un tasto premuto alla volta) e gli stati della levetta, così poi
        ogni tocco e ogni movimento si vede subito."""
        try:
            for premuto in (None, "k", "camera", "infrarossi", "media", "palette", "d", "x"):
                if self.ferma_precalcolo.is_set():
                    return
                self._variante(premuto)
            for selezionato in self.TASTI_GHIERA:
                if self.ferma_precalcolo.is_set():
                    return
                self.immagine(selezionato, None)
        except Exception as ex:
            print(f"[KINECT2-GUI] Precalcolo interrotto: {ex}")

    def _disegna_croce_x(self, img):
        """La X incisa sul tasto di chiusura (riflesso chiaro + segno scuro)."""
        x0, y0, x1, y1 = self.rett_x
        c = ((x0 + x1) / 2, (y0 + y1) / 2)
        d = (x1 - x0) * 0.24
        spess = max(2, int(0.014 * self.u * SS))
        for off, col in ((1.2, (0.97, 0.97, 0.97)), (0.0, (0.24, 0.23, 0.22))):
            for sx in (-1, 1):
                p1 = (int((c[0] - d + off) * SS), int((c[1] - d * sx + off) * SS))
                p2 = (int((c[0] + d + off) * SS), int((c[1] + d * sx + off) * SS))
                cv2.line(img, p1, p2, col, spess, cv2.LINE_AA)

    # --- dove ho toccato? ---------------------------------------------
    def tasto_in(self, x, y):
        dx, dy = x - self.cx, y - self.cy
        r = math.hypot(dx, dy)
        if r <= self.r_anello:
            return "k"
        if self.R_in - self.gap / 2 <= r <= self.R_out + 0.01 * self.u:
            if dy < 0:
                return "camera" if dx < 0 else "infrarossi"
            return "media" if dx < 0 else "palette"
        if math.hypot(x - self.c_d[0], y - self.c_d[1]) <= self.r_d * 1.25:
            return "d"
        x0, y0, x1, y1 = self.rett_x
        b = 0.02 * self.u
        if x0 - b <= x <= x1 + b and y0 - b <= y <= y1 + b:
            return "x"
        return None


def immagine_tk(bgr):
    ok, png = cv2.imencode(".png", bgr)
    return tk.PhotoImage(data=base64.b64encode(png.tobytes()).decode("ascii"))


# =====================================================================
# Processi: camere, Doom, bridge dei pulsanti fisici (come prima)
# =====================================================================
class GestoreProcessi:
    """Lancia una camera alla volta, nasconde la GUI finché è aperta, e
    chiama gli hook per cedere/riprendere i GPIO (come nella Camera 1)."""

    def __init__(self, root, prima, dopo, al_ritorno=None):
        self._root = root
        self._prima = prima
        self._dopo = dopo
        self._al_ritorno = al_ritorno
        self._processo = None

    def avvia_script(self, nome_script):
        percorso = os.path.join(CARTELLA_SCRIPT, nome_script)
        if not os.path.isfile(VENV_PYTHON) or not os.path.isfile(percorso):
            messagebox.showerror("Errore avvio", f"Non trovo:\n{VENV_PYTHON}\no\n{percorso}")
            return
        self.avvia_processo([VENV_PYTHON, "-u", percorso])

    def avvia_doom(self):
        if not os.path.isfile(COMANDO_DOOM):
            messagebox.showerror(
                "Errore avvio DOOM",
                f"Non trovo chocolate-doom qui:\n{COMANDO_DOOM}\n"
                "(sudo apt install chocolate-doom)")
            return
        if os.path.isfile(VENV_PYTHON) and os.path.isfile(SCRIPT_DOOM_PONTE):
            self.avvia_processo([VENV_PYTHON, "-u", SCRIPT_DOOM_PONTE])
        else:
            print("[KINECT2-GUI] doom_ponte.py non trovato: Doom senza comandi fisici")
            self.avvia_processo([COMANDO_DOOM])

    def avvia_processo(self, comando):
        if self._processo is not None and self._processo.poll() is None:
            return
        print(f"[KINECT2-GUI] Avvio {' '.join(comando)}")
        self._prima()
        try:
            # Tutto quello che il processo scrive finisce in kinect2_log.txt
            log = open(FILE_LOG, "w")
            self._processo = subprocess.Popen(comando, cwd=CARTELLA_SCRIPT,
                                              stdout=log, stderr=subprocess.STDOUT)
            log.close()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Errore avvio", f"Avvio fallito:\n{e}")
            self._dopo()
            return
        self._root.withdraw()
        self._controlla_fine()

    def _controlla_fine(self):
        if self._processo is not None and self._processo.poll() is None:
            self._root.after(500, self._controlla_fine)
        else:
            self._root.deiconify()
            if self._al_ritorno:
                self._al_ritorno()
            self._root.lift()
            self._dopo()

    def chiudi_tutto(self):
        if self._processo is not None and self._processo.poll() is None:
            self._processo.terminate()


class BridgeInputMenu:
    """Processo usa e getta che legge levetta e pulsanti nel menu
    (menu_input_bridge.py, con l'opzione --diagonali per la ghiera)."""

    def __init__(self):
        self._processo = None

    def avvia(self, gestore_riga):
        if not os.path.isfile(VENV_PYTHON) or not os.path.isfile(SCRIPT_MENU_INPUT_BRIDGE):
            print("[KINECT2-GUI] menu_input_bridge.py non trovato: solo comandi a tocco")
            return
        try:
            self._processo = subprocess.Popen(
                [VENV_PYTHON, SCRIPT_MENU_INPUT_BRIDGE, "--diagonali"],
                stdout=subprocess.PIPE, text=True, bufsize=1, cwd=CARTELLA_SCRIPT,
            )
        except Exception as e:
            print(f"[KINECT2-GUI] Bridge non avviato: {e}")
            return
        processo = self._processo

        def _leggi():
            for riga in processo.stdout:
                riga = riga.strip()
                if riga:
                    gestore_riga(riga)

        threading.Thread(target=_leggi, daemon=True).start()

    def ferma(self):
        if self._processo is not None:
            self._processo.terminate()
            try:
                self._processo.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._processo.kill()
            self._processo = None


def apri_cartella(percorso):
    """Apre la cartella nel file manager del Raspberry, senza aspettarlo:
    la GUI resta lì, la cartella si chiude con la sua X."""
    os.makedirs(os.path.join(percorso, "video"), exist_ok=True)
    os.makedirs(os.path.join(percorso, "foto"), exist_ok=True)
    for programma in ("pcmanfm", "pcmanfm-qt", "nautilus", "thunar", "xdg-open"):
        if shutil.which(programma):
            subprocess.Popen([programma, percorso], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[KINECT2-GUI] Apro {percorso} con {programma}")
            return True
    messagebox.showerror("Media", "Non trovo un file manager per aprire la cartella.")
    return False


# =====================================================================
# Applicazione
# =====================================================================
class AppKinectCamera2:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KINECT CAMERA 2")
        self.W, self.H = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{self.W}x{self.H}+0+0")
        self.root.configure(bg="#b8bcc1")
        # Schermo intero "gestito" (non overrideredirect): così la cartella
        # MEDIA, quando si apre, compare SOPRA la GUI e non sotto.
        self._schermo_intero()

        self.pannello = Pannello(self.W, self.H)
        self._foto = {}
        self.selezionato = "k"
        self.premuto = None

        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H,
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack(fill="both", expand=True)
        self.id_immagine = self.canvas.create_image(0, 0, anchor="nw")
        self._scritte()
        self._aggiorna_immagine()

        self.canvas.bind("<ButtonPress-1>", self._tocco_giu)
        self.canvas.bind("<ButtonRelease-1>", self._tocco_su)

        self.bridge = BridgeInputMenu()
        self.processi = GestoreProcessi(self.root, prima=self.bridge.ferma, dopo=self._avvia_bridge,
                                        al_ritorno=self._schermo_intero)
        self._avvia_bridge()
        self._aggiorna_tensione()
        self._thread_precalcolo = None
        self.root.after(200, self._precalcola)

    def _schermo_intero(self):
        try:
            self.root.attributes("-fullscreen", True)
        except tk.TclError:
            self.root.overrideredirect(True)

    # --- immagini -------------------------------------------------------
    def _foto_per(self, selezionato, premuto):
        chiave = (selezionato, premuto)
        if chiave not in self._foto:
            self._foto[chiave] = immagine_tk(self.pannello.immagine(selezionato, premuto))
        return self._foto[chiave]

    def _aggiorna_immagine(self):
        self.canvas.itemconfig(self.id_immagine, image=self._foto_per(self.selezionato, self.premuto))

    def _precalcola(self):
        """Le immagini pesanti si calcolano in un thread a parte (numpy e
        OpenCV lavorano in parallelo a Tk); le PhotoImage di Tk invece si
        creano solo qui nel thread principale, al bisogno."""
        self._thread_precalcolo = threading.Thread(target=self.pannello.precalcola, daemon=True)
        self._thread_precalcolo.start()

    # --- scritte (testo di Tk sopra l'immagine) -------------------------
    def _testo_inciso(self, x, y, testo, font, colore=TESTO_INCISO, luce=TESTO_LUCE, **kw):
        self.canvas.create_text(x + 1, y + 1, text=testo, font=font, fill=luce, **kw)
        return self.canvas.create_text(x, y, text=testo, font=font, fill=colore, **kw)

    def _testo_ad_arco(self, testo, angolo_centro, sopra):
        """Scrive 'testo' lungo l'arco della ghiera, lettera per lettera,
        ogni lettera ruotata secondo la curva (come nel disegno)."""
        p = self.pannello
        raggio = (p.R_in + p.R_out) / 2
        larghezza_spicchio = math.radians(90) * raggio * 0.78
        px = int(0.046 * p.u)
        while True:
            font = tkfont.Font(family="DejaVu Sans", size=-px, weight="bold")
            spaziatura = px * 0.14
            larghezze = [font.measure(c) + spaziatura for c in testo]
            totale = sum(larghezze) - spaziatura
            if totale <= larghezza_spicchio or px <= 10:
                break
            px -= 1
        # sopra: si legge da sinistra a destra andando in senso orario
        verso = -1 if sopra else 1
        theta = math.radians(angolo_centro) - verso * (totale / 2) / raggio
        for c, l in zip(testo, larghezze):
            th = theta + verso * (l - spaziatura) / 2 / raggio
            x = p.cx + raggio * math.cos(th)
            y = p.cy - raggio * math.sin(th)
            rot = math.degrees(th) - 90 if sopra else math.degrees(th) + 90
            self._testo_inciso(x, y, c, font, angle=rot)
            theta += verso * l / raggio

    def _scritte(self):
        p = self.pannello
        u = p.u
        self._testo_ad_arco("CAMERA", 135, sopra=True)
        self._testo_ad_arco("INFRAROSSI", 45, sopra=True)
        self._testo_ad_arco("MEDIA", 225, sopra=False)
        self._testo_ad_arco("PALETTE", 315, sopra=False)

        font_k = tkfont.Font(family="DejaVu Serif", size=-int(0.16 * u), weight="bold")
        self.canvas.create_text(p.cx + 2, p.cy + 2, text="K", font=font_k, fill="#0e0f10")
        self.canvas.create_text(p.cx, p.cy, text="K", font=font_k, fill=TESTO_K)

        font_d = tkfont.Font(family="DejaVu Sans", size=-int(0.07 * u), weight="bold")
        self._testo_inciso(p.c_d[0], p.c_d[1], "D", font_d, colore=TESTO_DOOM)

        # LCD della tensione: segmenti "spenti" in trasparenza + valore vero
        x0, y0, x1, y1 = p.rett_lcd
        font_lcd = tkfont.Font(family="DejaVu Sans Mono", size=-int(0.055 * u), weight="bold")
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.canvas.create_text(cx, cy, text="88.88V", font=font_lcd, fill=TESTO_LCD_SPENTO)
        self.id_volt = self.canvas.create_text(cx, cy, text="--.--V", font=font_lcd, fill=TESTO_LCD)

        # in basso a sinistra c'è il logo graffiato (disegnato nello sfondo,
        # vedi Pannello._graffia_logo): nessuna scritta.

        # badge cromato in basso a destra, tipo "30x OPTICAL ZOOM"
        bx, by, ax, ay = p.badge
        font_v2 = tkfont.Font(family="DejaVu Sans", size=-int(0.06 * u), weight="bold", slant="italic")
        font_badge = tkfont.Font(family="DejaVu Sans", size=-int(0.022 * u), weight="bold")
        self.canvas.create_text(bx - 0.035 * u, by, text="v2", font=font_v2, fill=TESTO_BADGE, anchor="e")
        self.canvas.create_text(bx - 0.02 * u, by - 0.013 * u, text="TIME OF", font=font_badge,
                                fill=TESTO_BADGE, anchor="w")
        self.canvas.create_text(bx - 0.02 * u, by + 0.015 * u, text="FLIGHT", font=font_badge,
                                fill=TESTO_BADGE, anchor="w")

    def _aggiorna_tensione(self):
        v = leggi_tensione_ingresso()
        self.canvas.itemconfig(self.id_volt, text=f"{v:5.2f}V" if v is not None else "--.--V")
        self.root.after(1000, self._aggiorna_tensione)

    # --- tocco ------------------------------------------------------------
    def _tocco_giu(self, evento):
        tasto = self.pannello.tasto_in(evento.x, evento.y)
        if tasto is None:
            return
        self.premuto = tasto
        if tasto in Pannello.TASTI_GHIERA:
            self.selezionato = tasto
        self._aggiorna_immagine()

    def _tocco_su(self, evento):
        premuto = self.premuto
        if premuto is None:
            return
        self.premuto = None
        self._aggiorna_immagine()
        if self.pannello.tasto_in(evento.x, evento.y) == premuto:  # rilasciato sopra lo stesso tasto
            self.root.after(10, self._esegui, premuto)

    # --- levetta e pulsanti fisici -------------------------------------------
    def _avvia_bridge(self):
        self.bridge.avvia(lambda riga: self.root.after(0, self._gestisci_riga, riga))

    def _gestisci_riga(self, riga):
        if riga == "SELEZIONA":
            # piccolo "click" visivo, poi l'azione
            self.premuto = self.selezionato
            self._aggiorna_immagine()
            self.root.after(140, self._rilascia_e_esegui)
        elif riga.startswith("MUOVI "):
            direzione = riga.split(" ", 1)[1]
            nuovo = NAVIGAZIONE[self.selezionato].get(direzione)
            if nuovo:
                self.selezionato = nuovo
                self._aggiorna_immagine()
        elif riga.startswith("ERRORE"):
            print(f"[KINECT2-GUI] {riga}")

    def _rilascia_e_esegui(self):
        tasto = self.premuto
        self.premuto = None
        self._aggiorna_immagine()
        if tasto:
            self._esegui(tasto)

    # --- azioni -----------------------------------------------------------
    def _esegui(self, tasto):
        print(f"[KINECT2-GUI] Tasto {tasto}")
        if tasto in SCRIPT_TASTI:
            self.processi.avvia_script(SCRIPT_TASTI[tasto])
        elif tasto == "media":
            apri_cartella(CARTELLA_MEDIA)
        elif tasto == "palette":
            pass  # per ora vuoto: ne parleremo
        elif tasto == "d":
            self.processi.avvia_doom()
        elif tasto == "x":
            self.chiudi()

    def chiudi(self):
        # Se il precalcolo sta ancora lavorando lo fermiamo con calma: uscire
        # mentre OpenCV è a metà di un calcolo fa terminare il processo male.
        self.pannello.ferma_precalcolo.set()
        t = getattr(self, "_thread_precalcolo", None)
        if t is not None and t.is_alive():
            t.join(timeout=3)
        self.processi.chiudi_tutto()
        self.bridge.ferma()
        self.root.destroy()

    def avvia(self):
        self.root.mainloop()


if __name__ == "__main__":
    AppKinectCamera2().avvia()
