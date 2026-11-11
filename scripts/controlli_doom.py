"""
controlli_doom.py
-------------------
Profilo comandi della modalità DOOM: traduce pulsanti fisici e levetta in
tasti di tastiera e click del mouse "finti", che Chocolate Doom riceve
come se arrivassero da una tastiera e un mouse USB veri.

Come funziona:
  Linux permette di creare periferiche di input virtuali (modulo "uinput").
  Ne creiamo due — una tastiera e un mouse — con la libreria python-evdev.
  Il sistema (anche sotto Wayland) le tratta come periferiche reali, quindi
  Doom non sa nemmeno che dietro ci sono i nostri pulsanti GPIO.

Separazione delle modalità:
  Questo file riguarda SOLO Doom. Il menu ha il suo profilo in
  menu_input_bridge.py, le camere in overlay_rec.py + collega_controlli_camera.
  Il collegamento pulsanti -> questo file lo fa input_fisico.collega_controlli_doom.

MAPPA COMANDI DOOM (modificabile nella tabella TASTI_TENUTI qui sotto):
    Rosso (REC)          -> click sinistro mouse  (spara; nei menu seleziona)
    Bianco (sinistra)    -> ,                     (passo laterale a sinistra)
    Nero (destra)        -> .                     (passo laterale a destra)
    LB                   -> Shift                 (corsa, finché lo tieni)
    Verde (giù)          -> Spazio                (apri porte / usa)
    Pressione levetta    -> Y                     (conferma "sì", es. uscita)
    Giallo (su)          -> arma successiva       (scatta al RILASCIO, vedi sotto)
    Bianco + Giallo      -> Esc                   (menu / pausa)
    Levetta su/giù       -> freccia su/giù        (avanti / indietro)
    Levetta sx/dx        -> freccia sx/dx         (gira la visuale)

Perché il giallo agisce al rilascio:
  È impossibile premere bianco e giallo nello stesso identico istante. Se
  il giallo cambiasse arma appena premuto, ogni volta che fai la combo per
  Esc cambieresti anche arma. Così invece: premi e rilasci il giallo da
  solo -> arma successiva; se mentre è giù premi anche il bianco -> Esc, e
  al rilascio il cambio arma viene saltato.
"""

import threading

from evdev import UInput, ecodes as e

# --- Tabella pulsante -> tasto (tenuto premuto finché tieni il pulsante) ---
TASTI_TENUTI = {
    "rec": e.BTN_LEFT,         # rosso: spara / seleziona nei menu
    "sinistra": e.KEY_COMMA,   # bianco: passo laterale sinistra
    "destra": e.KEY_DOT,       # nero: passo laterale destra
    "lb": e.KEY_RIGHTSHIFT,    # LB: corsa
    "giu": e.KEY_SPACE,        # verde: usa / apri porte
    "stick": e.KEY_Y,          # pressione levetta: "Y" (conferma uscita)
}

# Tasto "arma successiva". Doom non ne ha uno di default: configura_doom.py
# lo assegna a "]" nel file di configurazione di Chocolate Doom
# (key_nextweapon). Se lo cambi qui, cambialo anche lì.
TASTO_ARMA_SUCCESSIVA = e.KEY_RIGHTBRACE
TASTO_ESC = e.KEY_ESC

PULSANTE_ARMA = "su"           # giallo
COMBO_ESC = ("sinistra", "su")  # bianco + giallo

# Levetta -> frecce. Isteresi: la freccia si "preme" oltre SOGLIA_ON e si
# "rilascia" solo sotto SOGLIA_OFF, così vicino alla soglia non sfarfalla.
SOGLIA_ON = 0.5
SOGLIA_OFF = 0.35
FRECCE_Y = (e.KEY_UP, e.KEY_DOWN)      # (positivo, negativo): su = avanti
FRECCE_X = (e.KEY_RIGHT, e.KEY_LEFT)   # (positivo, negativo): destra = gira a destra

DURATA_TOCCO_S = 0.08  # quanto resta premuto un tasto "toccato" (Esc, arma)

# Tutto ciò che può inviare la tastiera virtuale (servono anche i tasti
# extra della config, per dichiararli al sistema alla creazione).
_TASTI_TASTIERA = sorted({
    c for c in TASTI_TENUTI.values() if c < e.BTN_MISC
} | {TASTO_ARMA_SUCCESSIVA, TASTO_ESC, *FRECCE_Y, *FRECCE_X})


def _nome_codice(codice):
    nome = e.KEY.get(codice) or e.BTN.get(codice) or str(codice)
    return nome[0] if isinstance(nome, (list, tuple)) else nome


class DispositiviVirtuali:
    """Tastiera + mouse virtuali (uinput). Richiede permesso di scrittura su
    /dev/uinput (vedi istruzioni in doom_ponte.py)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._tastiera = UInput({e.EV_KEY: _TASTI_TASTIERA},
                                name="kinectcam-doom-tastiera")
        # Un "mouse" per il sistema deve avere anche gli assi X/Y, anche se
        # non li muoviamo mai: senza, alcuni compositor non lo riconoscono.
        self._mouse = UInput({e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
                              e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL]},
                             name="kinectcam-doom-mouse")

    def invia(self, codice, premuto):
        dispositivo = self._mouse if e.BTN_MOUSE <= codice < e.BTN_JOYSTICK else self._tastiera
        with self._lock:
            dispositivo.write(e.EV_KEY, codice, 1 if premuto else 0)
            dispositivo.syn()

    def chiudi(self):
        for d in (self._tastiera, self._mouse):
            try:
                d.close()
            except Exception:
                pass


class ControlliDoom:
    """
    Logica del profilo Doom, indipendente dall'hardware: riceve eventi
    "pulsante premuto/rilasciato" e valori della levetta, e decide quali
    tasti premere/rilasciare sull'uscita (DispositiviVirtuali, o un finto
    oggetto nei test). Thread-safe: i pulsanti arrivano dal thread di
    gpiozero, la levetta dal ciclo principale.
    """

    def __init__(self, uscita, verboso=True):
        self._uscita = uscita
        self._verboso = verboso
        self._lock = threading.RLock()
        self._tasti_tenuti = set()       # codici che ABBIAMO premuto e non ancora rilasciato
        self._pulsanti_giu = set()       # pulsanti fisici attualmente premuti
        self._combo_usata = False        # la combo Esc è scattata durante questa pressione del giallo
        self._dir_x = 0
        self._dir_y = 0
        self._timer = []

    # --- primitive sui tasti -------------------------------------------
    def _log(self, testo):
        if self._verboso:
            print(f"[DOOM] {testo}", flush=True)

    def _premi(self, codice):
        if codice not in self._tasti_tenuti:
            self._tasti_tenuti.add(codice)
            self._uscita.invia(codice, True)

    def _rilascia(self, codice):
        if codice in self._tasti_tenuti:
            self._tasti_tenuti.discard(codice)
            self._uscita.invia(codice, False)

    def _tocca(self, codice):
        """Preme e, dopo DURATA_TOCCO_S, rilascia (senza bloccare il chiamante)."""
        self._premi(codice)

        def _fine():
            with self._lock:
                self._rilascia(codice)
        t = threading.Timer(DURATA_TOCCO_S, _fine)
        t.daemon = True
        self._timer = [x for x in self._timer if x.is_alive()]
        self._timer.append(t)
        t.start()

    # --- pulsanti ------------------------------------------------------
    def pulsante_premuto(self, nome):
        with self._lock:
            self._pulsanti_giu.add(nome)

            if nome in COMBO_ESC and all(p in self._pulsanti_giu for p in COMBO_ESC):
                self._combo_usata = True
                # Se il bianco aveva già iniziato il passo laterale, lo fermiamo.
                for p in COMBO_ESC:
                    codice = TASTI_TENUTI.get(p)
                    if codice is not None:
                        self._rilascia(codice)
                self._log("bianco + giallo -> Esc")
                self._tocca(TASTO_ESC)
                return

            if nome == PULSANTE_ARMA:
                self._combo_usata = False  # nuova pressione: decideremo al rilascio
                return

            codice = TASTI_TENUTI.get(nome)
            if codice is not None:
                self._log(f"{nome} premuto -> {_nome_codice(codice)}")
                self._premi(codice)

    def pulsante_rilasciato(self, nome):
        with self._lock:
            self._pulsanti_giu.discard(nome)

            if nome == PULSANTE_ARMA:
                if not self._combo_usata:
                    self._log("giallo -> arma successiva")
                    self._tocca(TASTO_ARMA_SUCCESSIVA)
                self._combo_usata = False
                return

            codice = TASTI_TENUTI.get(nome)
            if codice is not None:
                self._rilascia(codice)

    # --- levetta -------------------------------------------------------
    @staticmethod
    def _direzione(valore, attuale):
        if attuale == 1 and valore > SOGLIA_OFF:
            return 1
        if attuale == -1 and valore < -SOGLIA_OFF:
            return -1
        if valore > SOGLIA_ON:
            return 1
        if valore < -SOGLIA_ON:
            return -1
        return 0

    def _aggiorna_asse(self, attuale, nuova, frecce):
        if nuova == attuale:
            return
        positivo, negativo = frecce
        if attuale == 1:
            self._rilascia(positivo)
        elif attuale == -1:
            self._rilascia(negativo)
        if nuova == 1:
            self._premi(positivo)
        elif nuova == -1:
            self._premi(negativo)

    def aggiorna_levetta(self, x, y):
        """Da chiamare spesso (es. 100 volte al secondo) con i valori di
        input_fisico.leggi_levetta()."""
        with self._lock:
            nuova_x = self._direzione(x, self._dir_x)
            nuova_y = self._direzione(y, self._dir_y)
            self._aggiorna_asse(self._dir_x, nuova_x, FRECCE_X)
            self._aggiorna_asse(self._dir_y, nuova_y, FRECCE_Y)
            self._dir_x, self._dir_y = nuova_x, nuova_y

    # --- chiusura ------------------------------------------------------
    def rilascia_tutto(self):
        """Rilascia ogni tasto ancora premuto: da chiamare SEMPRE all'uscita,
        altrimenti il sistema potrebbe restare con un tasto 'incastrato'."""
        with self._lock:
            for t in self._timer:
                t.cancel()
            self._timer.clear()
            for codice in list(self._tasti_tenuti):
                self._rilascia(codice)
            self._pulsanti_giu.clear()
            self._dir_x = self._dir_y = 0
