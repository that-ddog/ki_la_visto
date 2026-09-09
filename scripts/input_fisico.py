"""
input_fisico.py
-----------------
Lettura dei pulsanti fisici (croce + REC + tasto levetta) e della levetta
analogica (via ADC ADS1115) sul Raspberry Pi 5.

Pin usati (BCM):
    UP     -> GPIO5   (pin fisico 29)
    DOWN   -> GPIO6   (pin fisico 31)
    LEFT   -> GPIO13  (pin fisico 33)
    RIGHT  -> GPIO19  (pin fisico 35)
    REC    -> GPIO26  (pin fisico 37)
    STICK  -> GPIO21  (pin fisico 40)   # tasto integrato nella levetta
    SDA    -> GPIO2   (pin fisico 3)    # I2C, fisso
    SCL    -> GPIO3   (pin fisico 5)    # I2C, fisso

Tutti i pulsanti sono cablati a massa comune (premuto = collegato a GND):
usiamo il pull-up interno del Raspberry Pi, quindi a riposo il pin legge
"alto" e premendo va a "basso" — gpiozero gestisce questo automaticamente
con pull_up=True.
"""

import board
import busio
from gpiozero import Button
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.ads1x15 import Pin
from adafruit_ads1x15.analog_in import AnalogIn

# --- Pulsanti digitali ------------------------------------------------
PIN_UP = 5
PIN_DOWN = 6
PIN_LEFT = 13
PIN_RIGHT = 19
PIN_REC = 26
PIN_STICK = 21

_BOUNCE = 0.05  # ignora rimbalzi meccanici del pulsante per 50ms

pulsanti = {
    "su": Button(PIN_UP, pull_up=True, bounce_time=_BOUNCE),
    "giu": Button(PIN_DOWN, pull_up=True, bounce_time=_BOUNCE),
    "sinistra": Button(PIN_LEFT, pull_up=True, bounce_time=_BOUNCE),
    "destra": Button(PIN_RIGHT, pull_up=True, bounce_time=_BOUNCE),
    "rec": Button(PIN_REC, pull_up=True, bounce_time=_BOUNCE),
    "stick": Button(PIN_STICK, pull_up=True, bounce_time=_BOUNCE),
}


# --- Levetta analogica (ADS1115 su I2C) --------------------------------
_i2c = busio.I2C(board.SCL, board.SDA)
_ads = ADS.ADS1115(_i2c)
_canale_x = AnalogIn(_ads, Pin.A0)
_canale_y = AnalogIn(_ads, Pin.A1)

# PLACEHOLDER — da ricalibrare col Kinect... ehm, con la levetta vera
# collegata: lancia test_input_fisico.py, guarda i valori raw stampati a
# riposo (levetta ferma al centro) e mettili qui come CENTRO_X/CENTRO_Y.
# FONDO_SCALA è quanto si sposta il valore raw dal centro al fondo corsa.
CENTRO_X = 13000
CENTRO_Y = 13000
FONDO_SCALA = 13000
ZONA_MORTA = 0.08  # 8%: sotto questa soglia consideriamo la levetta "ferma"


def leggi_levetta():
    """Ritorna (x, y) normalizzati fra -1.0 e 1.0, con zona morta al centro."""
    x = (_canale_x.value - CENTRO_X) / FONDO_SCALA
    y = (_canale_y.value - CENTRO_Y) / FONDO_SCALA
    x = max(-1.0, min(1.0, x))
    y = max(-1.0, min(1.0, y))
    if abs(x) < ZONA_MORTA:
        x = 0.0
    if abs(y) < ZONA_MORTA:
        y = 0.0
    return x, y


class GestoreComandi:
    """
    Il "cervello" che smista i pulsanti: ogni modalità (menu, camera, doom)
    registra le proprie funzioni per ciascun pulsante; il dispatcher guarda
    solo qual è la modalità attiva in questo momento e chiama la funzione
    giusta. Il codice dei pulsanti stessi non sa nulla di modalità.
    """

    def __init__(self):
        self.modalita_corrente = "menu"
        self.profili = {"menu": {}, "camera": {}, "doom": {}}

        for nome, pulsante in pulsanti.items():
            pulsante.when_pressed = self._crea_gestore(nome)

    def _crea_gestore(self, nome_pulsante):
        def gestore():
            profilo = self.profili.get(self.modalita_corrente, {})
            azione = profilo.get(nome_pulsante)
            if azione:
                azione()
            else:
                print(f"[INPUT] '{nome_pulsante}' premuto, nessuna azione in modalità '{self.modalita_corrente}'")
        return gestore

    def registra(self, modalita, nome_pulsante, funzione):
        """Assegna una funzione a un pulsante, valida solo per quella modalità."""
        self.profili.setdefault(modalita, {})[nome_pulsante] = funzione

    def imposta_modalita(self, modalita):
        print(f"[INPUT] Modalità comandi -> {modalita}")
        self.modalita_corrente = modalita
