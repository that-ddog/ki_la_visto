#!/usr/bin/env python3
"""
gui_kinect2_griglia.py  (VECCHIA GUI a griglia, tenuta come riserva)
----------------
GUI principale della "Kinect Camera 2" (Kinect v2). Stesso stile della GUI
della Kinect Camera 1: finestra a schermo intero senza bordi, barra in alto
con titolo, tensione e X per chiudere, e una griglia 2x2 con le 4 camere:

    CAMERA NORMALE | INFRAROSSI
    PROFONDITA'   | PROFONDITA' TURBO

Ogni pulsante lancia uno script separato (kinect2_*.py). Mentre la camera
è aperta la GUI si nasconde, e torna da sola quando la camera si chiude.
La "D" rossa in alto a sinistra avvia DOOM (via doom_ponte.py, con i
comandi fisici), esattamente come nella Kinect Camera 1.

Comandi: tocco/mouse sui pulsanti, oppure (se ci sono) levetta per
muoversi + pulsante VERDE (giù) per aprire. Nelle camere: X a tocco,
GIALLO (su) o Esc per tornare qui.

Per i pulsanti fisici riusa menu_input_bridge.py della Kinect Camera 1,
con lo stesso schema "processo usa e getta": va chiuso prima di aprire
una camera (che prende lei i GPIO) e rilanciato fresco al ritorno.
"""

import os
import shutil
import subprocess
import threading
import traceback
import tkinter as tk
from tkinter import messagebox

try:
    from overlay_rec import leggi_tensione_ingresso
except Exception:
    def leggi_tensione_ingresso():
        return None

CARTELLA_SCRIPT = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.expanduser("~/kinect-py311/bin/python3")
SCRIPT_MENU_INPUT_BRIDGE = os.path.join(CARTELLA_SCRIPT, "menu_input_bridge.py")
FILE_LOG = os.path.join(CARTELLA_SCRIPT, "kinect2_log.txt")

# DOOM: stesso meccanismo della Kinect Camera 1 (doom_ponte.py avvia
# chocolate-doom e traduce i pulsanti fisici in tasti).
SCRIPT_DOOM_PONTE = os.path.join(CARTELLA_SCRIPT, "doom_ponte.py")
COMANDO_DOOM = shutil.which("chocolate-doom") or "/usr/games/chocolate-doom"

CAMERE = [
    ("CAMERA\nNORMALE", "kinect2_camera_normale.py"),  # con REC (la vecchia kinect2_colore.py resta in cartella)
    ("INFRAROSSI", "kinect2_infrarossi2.py"),            # con REC (la vecchia resta in cartella)
    ("PROFONDITA'", "kinect2_profondita2.py"),          # con gamma + REC (la vecchia resta in cartella)
    ("PROFONDITA'\nTURBO", "kinect2_profondita_turbo2.py"),  # con gamma + REC (la vecchia resta in cartella)
]
RIGHE, COLONNE = 2, 2

# =====================================================================
# CONFIG — aspetto grafico (stesso tema grigio della Kinect Camera 1)
# =====================================================================
CONFIG = {
    "colore_sfondo": "#2b2b2b",
    "colore_barra": "#1c1c1c",
    "colore_bottone": "#474747",
    "colore_bottone_hover": "#5c5c5c",
    "colore_testo": "#f0f0f0",
    "colore_testo_barra": "#dddddd",
    "colore_chiudi_hover": "#c0392b",
    "colore_cursore_menu": "#4fc3f7",
    "colore_accento": "#4fc3f7",   # il "2" del titolo
    "colore_doom": "#ff3b30",      # la "D" di DOOM, rosso acceso come nella Camera 1

    "font_bottone": ("DejaVu Sans", 18, "bold"),
    "font_barra": ("DejaVu Sans", 14, "bold"),
    "font_titolo": ("DejaVu Sans", 12),

    "altezza_barra": 40,
    "padding_griglia": 8,
}


class GestoreProcessi:
    """Lancia una camera alla volta, nasconde la GUI finché è aperta, e
    chiama gli hook per cedere/riprendere i GPIO (come nella Camera 1)."""

    def __init__(self, root, prima, dopo):
        self._root = root
        self._prima = prima
        self._dopo = dopo
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
            # Come nella Kinect Camera 1: il ponte prende i pulsanti fisici,
            # li trasforma in tasti di Doom e avvia chocolate-doom.
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
            # (sovrascritto a ogni avvio): aperto dall'icona non c'è un
            # terminale, e senza log non si capirebbe cosa è andato storto.
            log = open(FILE_LOG, "w")
            self._processo = subprocess.Popen(comando, cwd=CARTELLA_SCRIPT,
                                              stdout=log, stderr=subprocess.STDOUT)
            log.close()  # il processo figlio ha la sua copia
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
            self._root.lift()
            self._dopo()

    def chiudi_tutto(self):
        if self._processo is not None and self._processo.poll() is None:
            self._processo.terminate()


class BridgeInputMenu:
    """Processo usa e getta che legge levetta e pulsanti nel menu
    (menu_input_bridge.py, lo stesso della Kinect Camera 1)."""

    def __init__(self):
        self._processo = None

    def avvia(self, gestore_riga):
        if not os.path.isfile(VENV_PYTHON) or not os.path.isfile(SCRIPT_MENU_INPUT_BRIDGE):
            print("[KINECT2-GUI] menu_input_bridge.py non trovato: solo comandi a tocco")
            return
        try:
            self._processo = subprocess.Popen(
                [VENV_PYTHON, SCRIPT_MENU_INPUT_BRIDGE],
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


class AppKinectCamera2:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KINECT CAMERA 2")
        self.root.configure(bg=CONFIG["colore_sfondo"])
        self.root.overrideredirect(True)
        self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")

        self.bridge = BridgeInputMenu()
        self.processi = GestoreProcessi(self.root, prima=self.bridge.ferma, dopo=self._avvia_bridge)

        self._crea_barra()
        self._crea_griglia()
        self._avvia_bridge()
        self._aggiorna_tensione()

    # --- input fisico -------------------------------------------------
    def _avvia_bridge(self):
        self.bridge.avvia(lambda riga: self.root.after(0, self._gestisci_riga, riga))

    def _gestisci_riga(self, riga):
        if riga == "SELEZIONA":
            self._apri(self._cursore)
        elif riga.startswith("MUOVI "):
            spostamenti = {"destra": (0, 1), "sinistra": (0, -1), "su": (-1, 0), "giu": (1, 0)}
            d = spostamenti.get(riga.split(" ", 1)[1])
            if d:
                r, c = divmod(self._cursore, COLONNE)
                r = max(0, min(RIGHE - 1, r + d[0]))
                c = max(0, min(COLONNE - 1, c + d[1]))
                self._cursore = r * COLONNE + c
                self._evidenzia()
        elif riga.startswith("ERRORE"):
            print(f"[KINECT2-GUI] {riga}")

    # --- barra superiore ----------------------------------------------
    def _crea_barra(self):
        barra = tk.Frame(self.root, bg=CONFIG["colore_barra"], height=CONFIG["altezza_barra"])
        barra.pack(side="top", fill="x")
        barra.pack_propagate(False)

        # "D" rossa in alto a sinistra = DOOM, come nella Kinect Camera 1.
        doom = tk.Label(barra, text=" D ", bg=CONFIG["colore_barra"], fg=CONFIG["colore_doom"],
                        font=CONFIG["font_barra"], cursor="hand2")
        doom.pack(side="left", padx=(10, 0))
        doom.bind("<Button-1>", lambda e: self.processi.avvia_doom())
        doom.bind("<Enter>", lambda e: doom.config(bg=CONFIG["colore_bottone_hover"]))
        doom.bind("<Leave>", lambda e: doom.config(bg=CONFIG["colore_barra"]))

        tk.Label(barra, text="KINECT CAMERA", bg=CONFIG["colore_barra"],
                 fg=CONFIG["colore_testo_barra"], font=CONFIG["font_titolo"]).pack(side="left", padx=(12, 4))
        tk.Label(barra, text="2", bg=CONFIG["colore_barra"],
                 fg=CONFIG["colore_accento"], font=CONFIG["font_barra"]).pack(side="left")

        chiudi = tk.Label(barra, text=" X ", bg=CONFIG["colore_barra"],
                          fg=CONFIG["colore_testo_barra"], font=CONFIG["font_barra"], cursor="hand2")
        chiudi.pack(side="right", padx=(0, 10))
        chiudi.bind("<Button-1>", lambda e: self.chiudi())
        chiudi.bind("<Enter>", lambda e: chiudi.config(bg=CONFIG["colore_chiudi_hover"]))
        chiudi.bind("<Leave>", lambda e: chiudi.config(bg=CONFIG["colore_barra"]))

        self.label_volt = tk.Label(barra, text="--V", bg=CONFIG["colore_barra"],
                                   fg=CONFIG["colore_testo_barra"], font=CONFIG["font_barra"])
        self.label_volt.pack(side="right", padx=(0, 6))

    def _aggiorna_tensione(self):
        v = leggi_tensione_ingresso()
        self.label_volt.config(text=f"{v:.2f}V" if v is not None else "--V")
        self.root.after(1000, self._aggiorna_tensione)

    # --- griglia 2x2 --------------------------------------------------
    def _crea_griglia(self):
        griglia = tk.Frame(self.root, bg=CONFIG["colore_sfondo"])
        griglia.pack(expand=True, fill="both",
                     padx=CONFIG["padding_griglia"], pady=CONFIG["padding_griglia"])
        for r in range(RIGHE):
            griglia.rowconfigure(r, weight=1, uniform="righe")
        for c in range(COLONNE):
            griglia.columnconfigure(c, weight=1, uniform="colonne")

        self._bottoni = []
        for i, (etichetta, _) in enumerate(CAMERE):
            b = tk.Button(
                griglia, text=etichetta, font=CONFIG["font_bottone"], justify="center",
                bg=CONFIG["colore_bottone"], fg=CONFIG["colore_testo"],
                activebackground=CONFIG["colore_bottone_hover"],
                activeforeground=CONFIG["colore_testo"],
                relief="flat", bd=0, highlightthickness=0,
                command=lambda i=i: self._apri(i),
            )
            r, c = divmod(i, COLONNE)
            b.grid(row=r, column=c, padx=CONFIG["padding_griglia"],
                   pady=CONFIG["padding_griglia"], sticky="nsew")
            self._bottoni.append(b)

        self._cursore = 0
        self._evidenzia()

    def _evidenzia(self):
        for i, b in enumerate(self._bottoni):
            if i == self._cursore:
                b.config(highlightthickness=4, highlightbackground=CONFIG["colore_cursore_menu"],
                         highlightcolor=CONFIG["colore_cursore_menu"])
            else:
                b.config(highlightthickness=0)

    def _apri(self, indice):
        self._cursore = indice
        self._evidenzia()
        self.processi.avvia_script(CAMERE[indice][1])

    def chiudi(self):
        self.processi.chiudi_tutto()
        self.bridge.ferma()
        self.root.destroy()

    def avvia(self):
        self.root.mainloop()


if __name__ == "__main__":
    AppKinectCamera2().avvia()
