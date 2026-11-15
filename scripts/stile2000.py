"""
stile2000.py
--------------
Gli "attrezzi da disegno" dello stile videocamera anni 2000, da usare per le
nuove schermate (per ora: Palette Experience). Stessi colori e stessa resa
del menu principale: alluminio spazzolato, tasti di plastica in rilievo con
ombra e smusso illuminato da in alto a sinistra, conche incassate.

Si disegna su una "tela" a risoluzione doppia (SS = 2) e alla fine si
rimpicciolisce: così i bordi vengono lisci. Ogni forma è una "maschera"
ritagliata attorno al pezzo, così i calcoli si fanno solo dove serve.

    tela = Tela(800, 480)
    img = tela.sfondo()                                  # alluminio spazzolato
    m = tela.rett(20, 20, 120, 70, raggio=8)             # forma del tasto
    tela.tasto(img, m, COLORI["tasto_alto"], COLORI["tasto_basso"])
    finale = tela.riduci(img)                            # immagine BGR 800x480
"""

import base64
import tkinter as tk

import cv2
import numpy as np

SS = 2  # risoluzione di disegno = SS volte quella dello schermo


def bgr(esadecimale):
    """'#RRGGBB' -> colore BGR in 0..1 (per il disegno con numpy/OpenCV)."""
    e = esadecimale.lstrip("#")
    r, g, b = int(e[0:2], 16), int(e[2:4], 16), int(e[4:6], 16)
    return np.array([b, g, r], np.float32) / 255.0


COLORI = {
    "sfondo_alto": bgr("#dcdee1"),      # argento chiaro (in alto)
    "sfondo_basso": bgr("#9ea3a9"),     # argento più scuro (in basso)
    "tasto_alto": bgr("#f1f2f3"),       # plastica argentata dei tasti
    "tasto_basso": bgr("#b4b9bf"),
    "incavo_alto": bgr("#8d9298"),      # conche scavate nel pannello
    "incavo_basso": bgr("#c3c7cc"),
}
TESTO_INCISO = "#3a3e44"        # scritte "incise" sulla plastica argentata
TESTO_LUCE = "#f7f8f9"          # riflesso chiaro sotto le scritte incise
TESTO_SPENTO = "#8f959c"        # scritta di un tasto non premibile


class Tela:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.u = min(H, W * 0.6)  # unità di misura: tutto scala con lo schermo
        self._margine = int(0.07 * self.u * SS)

    # --- sfondo ---------------------------------------------------------
    def sfondo(self):
        """Alluminio spazzolato, identico a quello del menu principale."""
        h, w = self.H * SS, self.W * SS
        t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        img = COLORI["sfondo_alto"] * (1 - t) + COLORI["sfondo_basso"] * t
        img = np.repeat(img, w, axis=1).astype(np.float32)
        rng = np.random.default_rng(2007)
        rumore = cv2.blur(rng.standard_normal((h, w)).astype(np.float32), (max(3, w // 5), 1))
        img += (rumore / (rumore.std() + 1e-6) * 0.016)[..., None]
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        img *= (1 - 0.18 * ((xs / w - 0.5) ** 2 + (ys / h - 0.5) ** 2))[..., None]
        return img

    # --- maschere -------------------------------------------------------
    def _maschera(self, x0, y0, x1, y1, disegna):
        """Crea la maschera di una forma dentro il rettangolo (x0..x1, y0..y1)
        in pixel di schermo. 'disegna(m, ox, oy)' riempie la forma su 'm'
        (coordinate SS, con origine spostata di ox, oy)."""
        M = self._margine
        ax0, ay0 = int(np.floor(x0 * SS)) - M, int(np.floor(y0 * SS)) - M
        ax1, ay1 = int(np.ceil(x1 * SS)) + M, int(np.ceil(y1 * SS)) + M
        m = np.zeros((ay1 - ay0, ax1 - ax0), np.uint8)
        disegna(m, ax0, ay0)
        m = cv2.GaussianBlur(m, (0, 0), 0.8)
        # ritaglio ai bordi della tela (i tasti vicino al bordo)
        cx0, cy0 = max(0, ax0), max(0, ay0)
        cx1, cy1 = min(self.W * SS, ax1), min(self.H * SS, ay1)
        m = m[cy0 - ay0:cy1 - ay0, cx0 - ax0:cx1 - ax0]
        interno = (int(y0 * SS) - cy0, int(y1 * SS) - cy0, int(x0 * SS) - cx0, int(x1 * SS) - cx0)
        return m, cx0, cy0, interno

    def rett(self, x0, y0, x1, y1, raggio=0.0):
        """Rettangolo con gli angoli arrotondati."""
        r = int(round(raggio * SS))

        def disegna(m, ox, oy):
            a = (int(round(x0 * SS)) - ox, int(round(y0 * SS)) - oy)
            b = (int(round(x1 * SS)) - ox, int(round(y1 * SS)) - oy)
            if r <= 0:
                cv2.rectangle(m, a, b, 255, -1)
                return
            cv2.rectangle(m, (a[0] + r, a[1]), (b[0] - r, b[1]), 255, -1)
            cv2.rectangle(m, (a[0], a[1] + r), (b[0], b[1] - r), 255, -1)
            for cx, cy in ((a[0] + r, a[1] + r), (b[0] - r, a[1] + r),
                           (a[0] + r, b[1] - r), (b[0] - r, b[1] - r)):
                cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
        return self._maschera(x0, y0, x1, y1, disegna)

    def cerchio(self, cx, cy, raggio):
        def disegna(m, ox, oy):
            cv2.circle(m, (int(round(cx * SS)) - ox, int(round(cy * SS)) - oy),
                       int(round(raggio * SS)), 255, -1, cv2.LINE_AA)
        return self._maschera(cx - raggio, cy - raggio, cx + raggio, cy + raggio, disegna)

    # --- il tasto -------------------------------------------------------
    def tasto(self, img, maschera, alto=None, basso=None, stile="rilievo",
              colore_fn=None, lucido=True):
        """Disegna un pezzo di plastica: ombra portata, corpo con sfumatura,
        smusso illuminato da in alto a sinistra.
        stile: 'rilievo' (normale), 'premuto' (schiacciato), 'incavo' (conca).
        colore_fn(x0, y0, w, h) -> immagine colore, per riempimenti speciali."""
        m8, x0, y0, (by0, by1, bx0, bx1) = maschera
        h, w = m8.shape
        if h == 0 or w == 0:
            return
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
        colore = colore_fn(x0, y0, w, h) if colore_fn is not None else alto * (1 - t) + basso * t

        mb = cv2.GaussianBlur(mf, (0, 0), 0.007 * u)
        luce = cv2.Sobel(mb, cv2.CV_32F, 1, 0, ksize=3) * 0.45 + cv2.Sobel(mb, cv2.CV_32F, 0, 1, ksize=3) * 0.9
        luce /= (np.abs(luce).max() + 1e-6)
        if stile in ("premuto", "incavo"):
            luce = -luce
        colore = colore + (1 - colore) * np.clip(luce, 0, 1)[..., None] * 0.6
        colore = colore * (1 - np.clip(-luce, 0, 1)[..., None] * 0.45)
        if stile == "rilievo" and lucido:
            colore = colore + 0.05 * (1 - t) ** 2
        if stile == "premuto":
            colore = colore * 0.88
        a = mf[..., None]
        roi[:] = roi * (1 - a) + np.clip(colore, 0, 1) * a

    # --- segni incisi (frecce, X, orologio...) ------------------------------
    def linea_incisa(self, img, punti, spessore, colore="#3a3e44", chiusa=False, sposta=0.0):
        """Una spezzata 'incisa': riflesso chiaro spostato di un pelo + segno
        scuro. punti in pixel di schermo; sposta = spostamento (tasto premuto)."""
        s = max(1, int(round(spessore * SS)))
        for extra, col in ((1.2, np.array([0.97, 0.97, 0.97])), (0.0, bgr(colore))):
            pts = np.array([[(x + sposta + extra) * SS, (y + sposta + extra) * SS] for x, y in punti])
            cv2.polylines(img, [np.round(pts * 16).astype(np.int32)], chiusa,
                          tuple(float(c) for c in col), s, cv2.LINE_AA, shift=4)

    def cerchio_inciso(self, img, cx, cy, raggio, spessore, colore="#3a3e44", sposta=0.0):
        s = max(1, int(round(spessore * SS)))
        for extra, col in ((1.2, np.array([0.97, 0.97, 0.97])), (0.0, bgr(colore))):
            c = (int(round((cx + sposta + extra) * SS * 16)), int(round((cy + sposta + extra) * SS * 16)))
            cv2.circle(img, c, int(round(raggio * SS * 16)), tuple(float(v) for v in col), s,
                       cv2.LINE_AA, shift=4)

    # --- uscita -----------------------------------------------------------
    def riduci(self, img):
        """Tela (o una sua striscia alta un multiplo di SS) -> immagine BGR 8 bit
        a misura di schermo."""
        h, w = img.shape[:2]
        piccola = cv2.resize(np.clip(img, 0, 1), (w // SS, h // SS), interpolation=cv2.INTER_AREA)
        return (piccola * 255).astype(np.uint8)

    def riduci_float(self, img):
        h, w = img.shape[:2]
        return cv2.resize(img, (w // SS, h // SS), interpolation=cv2.INTER_AREA)


def immagine_tk(immagine_bgr):
    """Immagine BGR 8 bit -> PhotoImage di Tk (compressione PNG leggera: veloce)."""
    ok, png = cv2.imencode(".png", immagine_bgr, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    return tk.PhotoImage(data=base64.b64encode(png.tobytes()).decode("ascii"))
