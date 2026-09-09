"""
input_fisico.py
-----------------
Lettura dei pulsanti fisici (croce + REC + tasto levetta) e della levetta
analogica (via ADC ADS1115) sul Raspberry Pi 5, più il "cervello" che
smista i comandi a seconda della modalità attiva (menu, camera, doom).

IMPORTANTE — gestione della risorsa GPIO/I2C:
Solo UN processo alla volta può tenere impegnati i pin GPIO e il bus I2C.
La GUI e le varie camere (depth_grigioN.py, video_normale.py,
camera_avanzata.py) sono processi SEPARATI, e solo uno per volta è "in
primo piano" (la GUI si nasconde quando apri una camera). Quindi:
  - ogni processo chiama inizializza() quando comincia a usare l'hardware
  - lo rilascia con termina() PRIMA di lasciare il posto a un altro
    processo (la GUI lo fa prima di lanciare una camera; una camera lo fa
    all'uscita, in un blocco finally)

Pin usati (BCM):
    UP     -> GPIO5   (pin fisico 29)
    DOWN   -> GPIO6   (pin fisico 31)
    LEFT   -> GPIO13  (pin fisico 33)
    RIGHT  -> GPIO19  (pin fisico 35)
    REC    -> GPIO26  (pin fisico 37)
    STICK  -> GPIO21  (pin fisico 40)   # tasto integrato nella levetta
    SDA    -> GPIO2   (pin fisico 3)    # I2C, fisso
    SCL    -> GPIO3   (pin fisico 5)    # I2C, fisso
"""

import time

PIN_UP = 5
PIN_DOWN = 6
PIN_LEFT = 13
PIN_RIGHT = 19
PIN_REC = 26
PIN_STICK = 21

_BOUNCE = 0.05

# Calibrazione levetta — aggiorna leggendo i valori raw stampati da
# test_input_fisico.py a levetta ferma al centro.
CENTRO_X = 13000
CENTRO_Y = 13000
FONDO_SCALA = 13000
ZONA_MORTA = 0.08

# Confermato dal test: "su" sulla levetta dava un valore invertito rispetto
# a quanto assunto — quindi lo correggiamo qui.
INVERTI_ASSE_Y = True

# --- Stato interno (popolato da inizializza(), svuotato da termina()) ----
_pulsanti = None
_canale_x = None
_canale_y = None


def inizializza():
    """Prende possesso dei GPIO e del bus I2C. Chiamala una volta sola per
    processo, prima di usare pulsanti/levetta. Ritorna un GestoreComandi
    già collegato all'hardware."""
    global _pulsanti, _canale_x, _canale_y

    import board
    import busio
    from gpiozero import Button
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.ads1x15 import Pin
    from adafruit_ads1x15.analog_in import AnalogIn

    _pulsanti = {
        "su": Button(PIN_UP, pull_up=True, bounce_time=_BOUNCE),
        "giu": Button(PIN_DOWN, pull_up=True, bounce_time=_BOUNCE),
        "sinistra": Button(PIN_LEFT, pull_up=True, bounce_time=_BOUNCE),
        "destra": Button(PIN_RIGHT, pull_up=True, bounce_time=_BOUNCE),
        "rec": Button(PIN_REC, pull_up=True, bounce_time=_BOUNCE),
        "stick": Button(PIN_STICK, pull_up=True, bounce_time=_BOUNCE),
    }

    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c)
    _canale_x = AnalogIn(ads, Pin.A0)
    _canale_y = AnalogIn(ads, Pin.A1)

    return GestoreComandi(_pulsanti)


def termina():
    """Rilascia GPIO e I2C, così un altro processo li può usare subito dopo."""
    global _pulsanti, _canale_x, _canale_y
    if _pulsanti:
        print(f"[INPUT] termina(): rilascio {len(_pulsanti)} pulsanti: {list(_pulsanti.keys())}")
        for nome, pulsante in _pulsanti.items():
            try:
                pulsante.close()
            except Exception as e:
                print(f"[INPUT] Avviso: rilascio di '{nome}' non riuscito: {e}")

        # Piccola pausa: gpiozero/lgpio girano un thread di sottofondo che
        # processa i cambiamenti sui pin. Se chiudiamo la pin_factory mentre
        # quel thread ha ancora un evento "in volo", va in errore e il
        # pulsante coinvolto può restare sordo da quel momento in poi in
        # questo processo. Diamogli un attimo per calmarsi prima di chiudere.
        time.sleep(0.15)

        # IMPORTANTE: chiudere i singoli Button non basta sempre. gpiozero
        # tiene una "pin factory" condivisa (l'accesso di basso livello al
        # chip GPIO) che può restare viva anche dopo aver chiuso ogni
        # pulsante, tenendo occupata la linea per un altro processo. La
        # chiudiamo esplicitamente per essere sicuri che si liberi davvero.
        try:
            from gpiozero import Device
            if Device.pin_factory is not None:
                Device.pin_factory.close()
                Device.pin_factory = None
                print("[INPUT] termina(): pin_factory chiusa")
        except Exception as e:
            print(f"[INPUT] Avviso: chiusura pin_factory non riuscita: {e}")

        time.sleep(0.05)
    else:
        print("[INPUT] termina(): _pulsanti era già vuoto/None, nulla da rilasciare")
    _pulsanti = None
    _canale_x = None
    _canale_y = None


def leggi_levetta():
    """Ritorna (x, y) normalizzati fra -1.0 e 1.0, con zona morta al centro.
    Se l'hardware non è disponibile (inizializza() fallita o mai chiamata),
    ritorna (0.0, 0.0) invece di far crashare lo script."""
    if _canale_x is None or _canale_y is None:
        return 0.0, 0.0
    x = (_canale_x.value - CENTRO_X) / FONDO_SCALA
    y = (_canale_y.value - CENTRO_Y) / FONDO_SCALA
    if INVERTI_ASSE_Y:
        y = -y
    x = max(-1.0, min(1.0, x))
    y = max(-1.0, min(1.0, y))
    if abs(x) < ZONA_MORTA:
        x = 0.0
    if abs(y) < ZONA_MORTA:
        y = 0.0
    return x, y


class GestoreComandi:
    """
    Smista i pulsanti fisici: ogni modalità (menu, camera, doom) registra
    le proprie funzioni; il dispatcher guarda solo qual è la modalità
    attiva e chiama la funzione giusta. Riconosce anche la combinazione
    "tutti i pulsanti insieme" per un'azione speciale (l'easter egg Doom).
    """

    def __init__(self, pulsanti):
        self.pulsanti = pulsanti
        self.modalita_corrente = "menu"
        self.profili = {"menu": {}, "camera": {}, "doom": {}}
        self.combo_tutti = {}  # una funzione per modalità, opzionale

        for nome, pulsante in pulsanti.items():
            pulsante.when_pressed = self._crea_gestore(nome)

    def _tutti_premuti(self):
        return all(p.is_pressed for p in self.pulsanti.values())

    def _crea_gestore(self, nome_pulsante):
        def gestore():
            if self._tutti_premuti():
                azione_combo = self.combo_tutti.get(self.modalita_corrente)
                if azione_combo:
                    azione_combo()
                    return
            profilo = self.profili.get(self.modalita_corrente, {})
            azione = profilo.get(nome_pulsante)
            if azione:
                azione()
        return gestore

    def registra(self, modalita, nome_pulsante, funzione):
        self.profili.setdefault(modalita, {})[nome_pulsante] = funzione

    def registra_combo_tutti(self, modalita, funzione):
        self.combo_tutti[modalita] = funzione

    def imposta_modalita(self, modalita):
        print(f"[INPUT] Modalità comandi -> {modalita}")
        self.modalita_corrente = modalita


def collega_controlli_camera(comandi, controlli):
    """
    Collegamento standard usato da tutti gli script "camera" (depth_grigioN,
    video_normale, camera_avanzata): registra i pulsanti fisici sulle
    STESSE azioni già disponibili via touch/mouse in ControlliOverlay
    (vedi overlay_rec.py), così i due modi di controllo restano coerenti.
    """
    comandi.imposta_modalita("camera")
    comandi.registra("camera", "rec", controlli.toggle_rec)
    comandi.registra("camera", "giu", controlli.toggle_pausa)
    comandi.registra("camera", "stick", controlli.scatta_foto)
    comandi.registra("camera", "su", controlli.chiedi_uscita)
    comandi.registra("camera", "sinistra", lambda: controlli.cambia_modo(-1))
    comandi.registra("camera", "destra", lambda: controlli.cambia_modo(+1))


def applica_levetta_gamma(controlli, velocita=0.03):
    """
    Da chiamare una volta per frame nel ciclo principale di uno script con
    la gamma (grigio3, grigio4, camera_avanzata): la levetta su/giù regola
    la gamma in modo continuo, proporzionale a quanto è inclinata. Non fa
    nulla se lo script non supporta la gamma.
    """
    if not controlli.con_gamma:
        return
    _, y = leggi_levetta()
    if y != 0.0:
        nuova = controlli.stato_gamma["gamma"] + y * velocita
        controlli.stato_gamma["gamma"] = round(
            max(controlli.gamma_min, min(controlli.gamma_max, nuova)), 3
        )
