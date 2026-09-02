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

import os
import subprocess
import traceback
import tkinter as tk
from tkinter import messagebox

# Percorsi verso l'interprete Python del venv e verso lo script depth grigio.
# Usiamo l'interprete del venv ESPLICITAMENTE (non il "python3" generico),
# così il pulsante funziona sempre, anche se la GUI fosse avviata in un modo
# che non ha già attivato il venv.
VENV_PYTHON = os.path.expanduser("~/kinect-py311/bin/python3")
SCRIPT_DEPTH_1 = os.path.expanduser("~/Desktop/ki_la_visto/scripts/depth_grigio1.py")
SCRIPT_DEPTH_2 = os.path.expanduser("~/Desktop/ki_la_visto/scripts/depth_grigio2.py")
SCRIPT_VIDEO_NORMALE = os.path.expanduser("~/Desktop/ki_la_visto/scripts/video_normale.py")

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
    "etichette": ["DEPTH CAMERA 1", "DEPTH CAMERA 2", "NORMAL CAMERA", "ALTRE FUNZIONI"],
}


# =====================================================================
# Funzioni "azione" — segnaposto per ora.
# Scritte indipendenti da chi le chiama (bottone touch, e in futuro
# magari un pulsante della levetta PS2), così restano riutilizzabili
# senza modifiche quando collegheremo la logica vera.
# =====================================================================
class GestoreProcessi:
    """
    Tiene traccia del processo esterno attualmente aperto (una qualunque
    delle viste Kinect: depth 1, depth 2, video normale...). Il Kinect è
    un dispositivo unico: evitiamo di aprire due viste insieme, qualunque
    combinazione. Nasconde la GUI principale mentre una vista è aperta e
    la rimostra da sola alla chiusura (ESC). È indipendente da Tkinter: in
    futuro potrà essere richiamato anche da un pulsante fisico/GPIO.
    """

    def __init__(self):
        self._processo_corrente = None
        self._root = None

    def imposta_finestra_principale(self, root):
        """Collega la finestra Tk principale, per poterla nascondere/rimostrare
        quando si apre/chiude una feature a schermo intero come una camera."""
        self._root = root

    def avvia_script(self, percorso_script):
        if self._processo_corrente is not None and self._processo_corrente.poll() is None:
            print("[AZIONE] C'è già una vista Kinect aperta: chiudila (ESC) prima di aprirne un'altra")
            return
        print(f"[AZIONE] Avvio: {VENV_PYTHON} {percorso_script}")
        if not os.path.isfile(VENV_PYTHON):
            messagebox.showerror(
                "Errore avvio",
                f"Non trovo l'interprete del venv qui:\n{VENV_PYTHON}",
            )
            return
        if not os.path.isfile(percorso_script):
            messagebox.showerror(
                "Errore avvio",
                f"Non trovo lo script qui:\n{percorso_script}",
            )
            return
        try:
            self._processo_corrente = subprocess.Popen([VENV_PYTHON, percorso_script])
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Errore avvio", f"Avvio fallito:\n{e}")
            return

        # Nascondiamo la GUI principale finché la vista è aperta, così la sua
        # finestra (che non è "overrideredirect") si vede sempre in primo
        # piano invece di restare nascosta dietro la nostra finestra kiosk.
        if self._root is not None:
            self._root.withdraw()
            self._controlla_fine_processo()

    def _controlla_fine_processo(self):
        """Controlla periodicamente se lo script è stato chiuso (es. con ESC);
        appena finisce, rimostra la GUI principale."""
        if self._processo_corrente is not None and self._processo_corrente.poll() is None:
            self._root.after(500, self._controlla_fine_processo)
        else:
            self._root.deiconify()
            self._root.lift()

    def chiudi_tutto(self):
        if self._processo_corrente is not None and self._processo_corrente.poll() is None:
            self._processo_corrente.terminate()


gestore_processi = GestoreProcessi()


def apri_depth_camera_1():
    gestore_processi.avvia_script(SCRIPT_DEPTH_1)


def apri_depth_camera_2():
    gestore_processi.avvia_script(SCRIPT_DEPTH_2)


def apri_normal_camera():
    gestore_processi.avvia_script(SCRIPT_VIDEO_NORMALE)


def apri_altre_funzioni():
    print("[AZIONE] Altre funzioni — da collegare")


def riduci_a_icona(finestra):
    finestra.iconify()


def chiudi_app(finestra):
    gestore_processi.chiudi_tutto()
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

        gestore_processi.imposta_finestra_principale(self.root)

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

        azioni = [apri_depth_camera_1, apri_depth_camera_2, apri_normal_camera, apri_altre_funzioni]
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
