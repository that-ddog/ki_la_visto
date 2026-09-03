#!/usr/bin/env python3
"""
gui_principale.py
------------------
GUI principale dell'app "Kinect Camera v1".

Griglia 2x4 (8 caselle): quattro modalità depth camera, la normal camera,
altre funzioni, e due caselle ancora vuote/disattivate, pronte per quando
decideremo cosa metterci.

Tutti i colori, i font e le dimensioni sono raccolti in CONFIG qui sotto:
per cambiare il tema basta modificare questo dizionario, senza toccare il
resto del codice.
"""

import os
import subprocess
import shutil
import traceback
import tkinter as tk
from tkinter import messagebox

# Percorsi verso l'interprete Python del venv e verso gli script Kinect.
# Usiamo l'interprete del venv ESPLICITAMENTE (non il "python3" generico),
# così i pulsanti funzionano sempre, anche se la GUI fosse avviata in un modo
# che non ha già attivato il venv.
VENV_PYTHON = os.path.expanduser("~/kinect-py311/bin/python3")
SCRIPT_DEPTH_1 = os.path.expanduser("~/Desktop/ki_la_visto/scripts/depth_grigio1.py")
SCRIPT_DEPTH_2 = os.path.expanduser("~/Desktop/ki_la_visto/scripts/depth_grigio2.py")
SCRIPT_DEPTH_3 = os.path.expanduser("~/Desktop/ki_la_visto/scripts/depth_grigio3.py")
SCRIPT_DEPTH_4 = os.path.expanduser("~/Desktop/ki_la_visto/scripts/depth_grigio4.py")
SCRIPT_VIDEO_NORMALE = os.path.expanduser("~/Desktop/ki_la_visto/scripts/video_normale.py")

# chocolate-doom è un pacchetto di sistema (non vive nel venv): lo cerchiamo
# nel PATH, con un percorso di riserva nel caso non venisse trovato lì.
COMANDO_DOOM = shutil.which("chocolate-doom") or "/usr/games/chocolate-doom"

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
    "colore_doom": "#ff3b30",           # rosso acceso per l'easter egg DOOM

    # Caselle ancora vuote/disattivate (le due in fondo alla griglia)
    "colore_bottone_vuoto": "#333333",
    "colore_testo_vuoto": "#666666",

    # Font
    "font_bottone": ("DejaVu Sans", 15, "bold"),  # ridotto un filo: ora ci sono 4 colonne
    "font_barra": ("DejaVu Sans", 14, "bold"),
    "font_titolo": ("DejaVu Sans", 12),

    # Dimensioni
    "altezza_barra": 40,
    "padding_griglia": 10,
    "bordo_bottone": 0,   # spessore bordo bottoni (0 = piatto/flat)

    # Testo (8 etichette per la griglia 2x4; "\n" va a capo dentro il pulsante,
    # utile perché con 4 colonne lo spazio orizzontale è poco. Le ultime due
    # vuote = caselle disattivate.
    "titolo_finestra": "KINECT CAMERA",
    "etichette": [
        "DEPTH\nCAMERA 1", "DEPTH\nCAMERA 2", "DEPTH\nCAMERA 3", "DEPTH\nCAMERA 4",
        "NORMAL\nCAMERA", "ALTRE\nFUNZIONI", "", "",
    ],
}


# =====================================================================
# Funzioni "azione".
# Scritte indipendenti da chi le chiama (bottone touch, e in futuro
# magari un pulsante della levetta PS2), così restano riutilizzabili
# senza modifiche quando collegheremo la logica vera.
# =====================================================================
class GestoreProcessi:
    """
    Tiene traccia del processo esterno attualmente aperto (una qualunque
    delle viste Kinect: depth 1-4, video normale...). Il Kinect è un
    dispositivo unico: evitiamo di aprire due viste insieme, qualunque
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
        self.avvia_processo([VENV_PYTHON, percorso_script])

    def avvia_doom(self):
        if not os.path.isfile(COMANDO_DOOM):
            messagebox.showerror(
                "Errore avvio DOOM",
                f"Non trovo l'eseguibile chocolate-doom qui:\n{COMANDO_DOOM}\n"
                "Verifica che sia installato (sudo apt install chocolate-doom).",
            )
            return
        self.avvia_processo([COMANDO_DOOM])

    def avvia_processo(self, comando):
        """comando: lista tipo ['chocolate-doom'] oppure [VENV_PYTHON, percorso_script]."""
        if self._processo_corrente is not None and self._processo_corrente.poll() is None:
            print("[AZIONE] C'è già qualcosa in esecuzione: chiudilo prima di aprire altro")
            return
        print(f"[AZIONE] Avvio: {' '.join(comando)}")
        try:
            self._processo_corrente = subprocess.Popen(comando)
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


def apri_depth_camera_3():
    gestore_processi.avvia_script(SCRIPT_DEPTH_3)


def apri_depth_camera_4():
    gestore_processi.avvia_script(SCRIPT_DEPTH_4)


def apri_normal_camera():
    gestore_processi.avvia_script(SCRIPT_VIDEO_NORMALE)


def apri_doom():
    gestore_processi.avvia_doom()


def apri_altre_funzioni():
    print("[AZIONE] Altre funzioni — da collegare")


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

        # Finestra senza bordi/barra di sistema: la barra la disegniamo noi.
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

        btn_doom = tk.Label(
            barra,
            text=" D ",
            bg=CONFIG["colore_barra"],
            fg=CONFIG["colore_doom"],
            font=CONFIG["font_barra"],
            cursor="hand2",
        )
        btn_doom.pack(side="left", padx=(10, 0))
        btn_doom.bind("<Button-1>", lambda e: apri_doom())
        btn_doom.bind("<Enter>", lambda e: btn_doom.config(bg=CONFIG["colore_bottone_hover"]))
        btn_doom.bind("<Leave>", lambda e: btn_doom.config(bg=CONFIG["colore_barra"]))

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

    # --- Griglia 2x4 di bottoni principali ---------------------------
    def _crea_griglia_bottoni(self):
        contenitore = tk.Frame(self.root, bg=CONFIG["colore_sfondo"])
        contenitore.pack(expand=True, fill="both",
                          padx=CONFIG["padding_griglia"], pady=CONFIG["padding_griglia"])

        for i in range(2):
            contenitore.rowconfigure(i, weight=1)
        for i in range(4):
            contenitore.columnconfigure(i, weight=1)

        # None = casella vuota/disattivata (le ultime due, per ora)
        azioni = [
            apri_depth_camera_1,
            apri_depth_camera_2,
            apri_depth_camera_3,
            apri_depth_camera_4,
            apri_normal_camera,
            apri_altre_funzioni,
            None,
            None,
        ]
        etichette = CONFIG["etichette"]
        posizioni = [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3)]

        for (riga, colonna), etichetta, azione in zip(posizioni, etichette, azioni):
            attiva = azione is not None
            bottone = tk.Button(
                contenitore,
                text=etichetta if attiva else "",
                font=CONFIG["font_bottone"],
                justify="center",
                bg=CONFIG["colore_bottone"] if attiva else CONFIG["colore_bottone_vuoto"],
                fg=CONFIG["colore_testo"] if attiva else CONFIG["colore_testo_vuoto"],
                activebackground=CONFIG["colore_bottone_hover"],
                activeforeground=CONFIG["colore_testo"],
                relief="flat",
                bd=CONFIG["bordo_bottone"],
                command=azione if attiva else None,
                state="normal" if attiva else "disabled",
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
