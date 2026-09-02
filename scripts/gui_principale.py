#!/usr/bin/env python3
"""
gui_principale.py
------------------
GUI principale dell'app "Kinect Camera v1" - PROTOTIPO GRAFICO.

Oggi ci occupiamo SOLO della grafica: quattro pulsanti (Depth Camera,
Normal Camera, Media, Altre Funzioni) e una barra superiore custom con
pulsanti per ridurre a icona e chiudere. Le funzioni collegate ai pulsanti
sono ancora dei segnaposto (stampano solo un messaggio in console): le
riempiremo di logica vera nei prossimi passaggi.

Tutti i colori, i font e le dimensioni sono raccolti in CONFIG qui sotto:
per cambiare il tema basta modificare questo dizionario, senza toccare il
resto del codice.
"""

import tkinter as tk

# =====================================================================
# CONFIG — tutto ciò che riguarda l'aspetto grafico sta qui.
# Cambia questi valori per modificare colori, font, dimensioni.
# =====================================================================
CONFIG = {
    # Colori tema "grigio" (provvisorio, facile da sostituire dopo)
    "colore_sfondo": "#2b2b2b",         # sfondo finestra
    "colore_barra": "#1c1c1c",          # barra superiore
    "colore_bottone": "#474747",        # bottoni principali
    "colore_bottone_hover": "#5c5c5c",  # bottoni al tocco/passaggio mouse
    "colore_testo": "#f0f0f0",          # testo bottoni
    "colore_testo_barra": "#dddddd",    # testo/icone barra superiore
    "colore_chiudi_hover": "#c0392b",   # rosso quando si sfiora la X

    # Font
    "font_bottone": ("DejaVu Sans", 18, "bold"),
    "font_barra": ("DejaVu Sans", 14, "bold"),
    "font_titolo": ("DejaVu Sans", 12),

    # Dimensioni
    "altezza_barra": 40,
    "padding_griglia": 14,
    "bordo_bottone": 0,   # spessore bordo bottoni (0 = piatto/flat)

    # Testo
    "titolo_finestra": "KINECT CAMERA",
    "etichette": ["DEPTH CAMERA", "NORMAL CAMERA", "MEDIA", "ALTRE FUNZIONI"],
}


# =====================================================================
# Funzioni "azione" — segnaposto per ora.
# Scritte indipendenti da chi le chiama (bottone touch, e in futuro
# magari un pulsante della levetta PS2), così restano riutilizzabili
# senza modifiche quando collegheremo la logica vera.
# =====================================================================
def apri_depth_camera():
    print("[AZIONE] Depth camera — da collegare")


def apri_normal_camera():
    print("[AZIONE] Normal camera — da collegare")


def apri_media():
    print("[AZIONE] Media — da collegare")


def apri_altre_funzioni():
    print("[AZIONE] Altre funzioni — da collegare")


def riduci_a_icona(finestra):
    finestra.iconify()


def chiudi_app(finestra):
    finestra.destroy()


# =====================================================================
# Costruzione della finestra
# =====================================================================
class AppKinectCamera:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(CONFIG["titolo_finestra"])
        self.root.configure(bg=CONFIG["colore_sfondo"])

        # Finestra senza bordi/barra di sistema: la barra la disegniamo noi,
        # così su un touchscreen senza tastiera si può sempre chiudere/ridurre.
        self.root.overrideredirect(True)

        larghezza = self.root.winfo_screenwidth()
        altezza = self.root.winfo_screenheight()
        self.root.geometry(f"{larghezza}x{altezza}+0+0")

        self._crea_barra_superiore()
        self._crea_griglia_bottoni()

    # --- Barra superiore custom -------------------------------------
    def _crea_barra_superiore(self):
        barra = tk.Frame(
            self.root,
            bg=CONFIG["colore_barra"],
            height=CONFIG["altezza_barra"],
        )
        barra.pack(side="top", fill="x")
        barra.pack_propagate(False)

        titolo = tk.Label(
            barra,
            text=CONFIG["titolo_finestra"],
            bg=CONFIG["colore_barra"],
            fg=CONFIG["colore_testo_barra"],
            font=CONFIG["font_titolo"],
        )
        titolo.pack(side="left", padx=12)

        btn_chiudi = tk.Label(
            barra,
            text=" X ",
            bg=CONFIG["colore_barra"],
            fg=CONFIG["colore_testo_barra"],
            font=CONFIG["font_barra"],
            cursor="hand2",
        )
        btn_chiudi.pack(side="right", padx=(0, 10))
        btn_chiudi.bind("<Button-1>", lambda e: chiudi_app(self.root))
        btn_chiudi.bind("<Enter>", lambda e: btn_chiudi.config(bg=CONFIG["colore_chiudi_hover"]))
        btn_chiudi.bind("<Leave>", lambda e: btn_chiudi.config(bg=CONFIG["colore_barra"]))

        btn_riduci = tk.Label(
            barra,
            text=" – ",
            bg=CONFIG["colore_barra"],
            fg=CONFIG["colore_testo_barra"],
            font=CONFIG["font_barra"],
            cursor="hand2",
        )
        btn_riduci.pack(side="right", padx=(0, 4))
        btn_riduci.bind("<Button-1>", lambda e: riduci_a_icona(self.root))
        btn_riduci.bind("<Enter>", lambda e: btn_riduci.config(bg=CONFIG["colore_bottone_hover"]))
        btn_riduci.bind("<Leave>", lambda e: btn_riduci.config(bg=CONFIG["colore_barra"]))

    # --- Griglia 2x2 di bottoni principali ---------------------------
    def _crea_griglia_bottoni(self):
        contenitore = tk.Frame(self.root, bg=CONFIG["colore_sfondo"])
        contenitore.pack(expand=True, fill="both",
                          padx=CONFIG["padding_griglia"], pady=CONFIG["padding_griglia"])

        for i in range(2):
            contenitore.rowconfigure(i, weight=1)
            contenitore.columnconfigure(i, weight=1)

        azioni = [apri_depth_camera, apri_normal_camera, apri_media, apri_altre_funzioni]
        etichette = CONFIG["etichette"]
        posizioni = [(0, 0), (0, 1), (1, 0), (1, 1)]

        for (riga, colonna), etichetta, azione in zip(posizioni, etichette, azioni):
            bottone = tk.Button(
                contenitore,
                text=etichetta,
                font=CONFIG["font_bottone"],
                bg=CONFIG["colore_bottone"],
                fg=CONFIG["colore_testo"],
                activebackground=CONFIG["colore_bottone_hover"],
                activeforeground=CONFIG["colore_testo"],
                relief="flat",
                bd=CONFIG["bordo_bottone"],
                command=azione,
            )
            bottone.grid(
                row=riga, column=colonna,
                padx=CONFIG["padding_griglia"], pady=CONFIG["padding_griglia"],
                sticky="nsew",
            )

    def avvia(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = AppKinectCamera()
    app.avvia()
