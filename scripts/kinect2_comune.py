"""
kinect2_comune.py
-------------------
Parti in comune a tutte le camere della "Kinect Camera 2" (Kinect v2):
  - carica libfreenect2 da ~/freenect2/lib (così NON serve più scrivere
    LD_LIBRARY_PATH=... davanti al comando)
  - apre il Kinect calcolando la profondità sulla GPU (OpenGL), con
    ripiego automatico sulla CPU se la GPU non parte
  - mostra le immagini a schermo intero con una X in alto a destra da
    toccare per uscire
  - pulsanti fisici (se presenti): il GIALLO (su) chiude la camera, come
    sulla Kinect Camera 1
  - funzioni di conversione (profondità -> grigio, infrarossi -> grigio...)

Regola d'oro: la finestra deve SEMPRE rispondere. Se il Kinect non parte o
non manda immagini, a schermo compare un messaggio e la X, Esc e il giallo
funzionano comunque. Ogni passaggio viene scritto nel log (terminale, o
kinect2_log.txt quando la camera è aperta dalla GUI).

Ogni script camera (kinect2_colore.py, kinect2_infrarossi.py, ...) chiama
solo esegui_camera() passandogli quali flussi accendere e come trasformare
i frame in un'immagine.

Opzione da riga di comando valida per tutte le camere:
    --cpu   forza il calcolo della profondità sulla CPU (lento, ~6 fps)
"""

import ctypes
import glob
import os
import signal
import sys
import threading
import time

USA_CPU = "--cpu" in sys.argv
if not USA_CPU:
    # La GPU del Pi 5 dichiara OpenGL 3.1, i programmi di libfreenect2
    # chiedono 3.3: diciamo al driver di dichiarare 3.3 (testato: regge).
    # Va impostato PRIMA che venga creato il contesto OpenGL.
    os.environ.setdefault("MESA_GL_VERSION_OVERRIDE", "3.3")
    os.environ.setdefault("MESA_GLSL_VERSION_OVERRIDE", "330")

import cv2
import numpy as np

CARTELLA_LIBFREENECT2 = os.path.expanduser("~/freenect2/lib")

# Profondità del Kinect v2: affidabile circa da 0.5 a 4.5 metri.
DISTANZA_MIN_MM = 500.0
DISTANZA_MAX_MM = 4500.0

# Infrarossi: valore grezzo che diventa "bianco" (alzalo se l'IR è bruciato,
# abbassalo se è troppo scuro).
IR_BIANCO = 20000.0

# Il colore arriva a 1920x1080: lo rimpiccioliamo prima di mostrarlo, tanto
# lo schermo è piccolo, e così il Pi fa meno fatica.
LARGHEZZA_COLORE_MOSTRATO = 960

# Dopo quanti secondi senza immagini suggeriamo di riavviare il Kinect.
SECONDI_PRIMA_DEL_CONSIGLIO = 8


def _log(testo):
    print(f"[KINECT2 {time.strftime('%H:%M:%S')}] {testo}", flush=True)


# --- Conversioni -----------------------------------------------------------
def colore_in_bgr(bgrx):
    bgr = bgrx[:, :, :3]
    h = int(round(LARGHEZZA_COLORE_MOSTRATO * bgr.shape[0] / bgr.shape[1]))
    return cv2.resize(bgr, (LARGHEZZA_COLORE_MOSTRATO, h), interpolation=cv2.INTER_LINEAR)


def ir_in_grigio(ir):
    norm = np.clip(ir / IR_BIANCO, 0.0, 1.0)
    return (np.sqrt(norm) * 255).astype(np.uint8)


def profondita_in_grigio(depth):
    """mm -> grigio: vicino = chiaro, lontano = scuro, niente dato = nero."""
    valida = depth > 0
    clip = np.clip(depth, DISTANZA_MIN_MM, DISTANZA_MAX_MM)
    grigio = 255 - (clip - DISTANZA_MIN_MM) * (255.0 / (DISTANZA_MAX_MM - DISTANZA_MIN_MM))
    grigio = grigio.astype(np.uint8)
    grigio[~valida] = 0
    return grigio


def profondita_a_colori(depth, colormap=cv2.COLORMAP_TURBO):
    grigio = profondita_in_grigio(depth)
    colorata = cv2.applyColorMap(grigio, colormap)
    colorata[grigio == 0] = 0
    return colorata


# --- Disegno: X per uscire e schermate di messaggio --------------------------
def _lato_x(img):
    return max(28, img.shape[1] // 14)


def disegna_x(img):
    """Disegna la X di uscita in alto a destra (ritorna l'immagine BGR)."""
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    lato = _lato_x(img)
    w = img.shape[1]
    x0, y0, x1, y1 = w - lato, 0, w, lato
    cv2.rectangle(img, (x0, y0), (x1, y1), (40, 40, 40), -1)
    m = lato // 4
    spessore = max(2, lato // 12)
    cv2.line(img, (x0 + m, y0 + m), (x1 - m, y1 - m), (255, 255, 255), spessore, cv2.LINE_AA)
    cv2.line(img, (x0 + m, y1 - m), (x1 - m, y0 + m), (255, 255, 255), spessore, cv2.LINE_AA)
    return img


def schermata_messaggio(righe, colore_testo=(255, 255, 255)):
    """Immagine nera 512x424 con qualche riga di testo: la mostriamo quando
    non ci sono ancora frame, così la finestra non resta mai 'morta'."""
    img = np.zeros((424, 512, 3), np.uint8)
    y = 150
    for riga in righe:
        cv2.putText(img, riga, (24, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colore_testo, 1, cv2.LINE_AA)
        y += 32
    return img


# --- Kinect ------------------------------------------------------------------
def _carica_libfreenect2():
    """Carica libfreenect2.so a mano: il modulo Python la cerca solo nelle
    cartelle di sistema, ma noi l'abbiamo installata in ~/freenect2/lib."""
    candidati = sorted(glob.glob(os.path.join(CARTELLA_LIBFREENECT2, "libfreenect2.so.*")))
    for percorso in candidati:
        try:
            ctypes.CDLL(percorso, mode=ctypes.RTLD_GLOBAL)
            _log(f"Caricata {percorso}")
            return
        except OSError as ex:
            _log(f"Non riesco a caricare {percorso}: {ex}")
    _log(f"Nessuna libfreenect2 in {CARTELLA_LIBFREENECT2}: provo quella di sistema")


def _crea_pipeline(profondita):
    """Crea la pipeline (GPU o CPU). Va chiamata nel thread PRINCIPALE e
    prima di aprire la finestra OpenCV: la pipeline GPU crea un contesto
    OpenGL, e così rispettiamo lo stesso ordine dei test che funzionavano."""
    _carica_libfreenect2()
    from pylibfreenect2 import (CpuPacketPipeline, createConsoleLogger,
                                setGlobalLogger, LoggerLevel)
    # Livello Info: messaggi di libfreenect2 dettagliati nel log, per capire
    # dove si ferma se qualcosa non va.
    setGlobalLogger(createConsoleLogger(LoggerLevel.Info))

    # La GPU serve solo per la profondità: per il solo colore usiamo la CPU
    # (la decodifica JPEG la fa comunque la CPU) ed evitiamo di aprire OpenGL.
    if profondita and not USA_CPU:
        try:
            from pylibfreenect2 import OpenGLPacketPipeline
            return OpenGLPacketPipeline(), "GPU (OpenGL)"
        except Exception as ex:
            _log(f"GPU non disponibile ({ex}): uso la CPU.")
    return CpuPacketPipeline(), "CPU"


def _apri_kinect(pipeline, nome_pipeline, colore, profondita):
    from pylibfreenect2 import Freenect2, SyncMultiFrameListener, FrameType

    _log("Cerco il Kinect...")
    fn = Freenect2()
    if fn.enumerateDevices() == 0:
        raise RuntimeError("Nessun Kinect v2 trovato (alimentatore? porta blu?)")
    serial = fn.getDeviceSerialNumber(0)

    _log("Apro il Kinect...")
    device = fn.openDevice(serial, pipeline=pipeline)
    tipi = 0
    if colore:
        tipi |= FrameType.Color
    if profondita:
        tipi |= FrameType.Ir | FrameType.Depth
    listener = SyncMultiFrameListener(tipi)
    if colore:
        device.setColorFrameListener(listener)
    if profondita:
        device.setIrAndDepthFrameListener(listener)
    _log(f"Avvio i flussi (colore={colore}, profondita={profondita})...")
    device.startStreams(colore, profondita)
    _log(f"Kinect v2 {serial.decode() if isinstance(serial, bytes) else serial} "
         f"avviato, pipeline {nome_pipeline}")
    # fn va tenuto vivo finché il device è in uso
    return fn, device, listener


def _chiudi_kinect_con_timeout(device, secondi=3.0):
    """device.stop()/close() con un limite di tempo: se l'USB è bloccata
    possono restare appese per sempre, e allora non si tornerebbe più alla
    GUI. Ritorna False se la chiusura non è finita in tempo."""

    def _chiudi():
        try:
            device.stop()
            device.close()
        except Exception as ex:
            _log(f"Chiusura Kinect: {ex}")

    t = threading.Thread(target=_chiudi, daemon=True)
    t.start()
    t.join(secondi)
    if t.is_alive():
        _log("Il Kinect non risponde alla chiusura: esco lo stesso.")
        return False
    return True


def _collega_pulsanti(chiedi_uscita):
    """Pulsanti fisici della Kinect Camera, se disponibili: giallo = esci.
    Ritorna True se l'hardware è stato preso (da rilasciare all'uscita)."""
    try:
        import input_fisico
        comandi = input_fisico.inizializza()
        comandi.imposta_modalita("camera")
        comandi.registra("camera", "su", chiedi_uscita)
        _log("Pulsanti fisici collegati (giallo = esci)")
        return True
    except Exception as ex:
        _log(f"Pulsanti fisici non disponibili ({ex}): esci con la X o con Esc.")
        return False


def _su_sigterm(signum, frame):
    raise SystemExit(0)


# --- Ciclo principale ----------------------------------------------------
def esegui_camera(nome_finestra, colore, profondita, elabora):
    """
    nome_finestra: titolo della finestra
    colore / profondita: quali flussi accendere (True/False)
    elabora: funzione che riceve un dict {"color": array, "ir": array,
             "depth": array} (solo le chiavi dei flussi accesi) e ritorna
             l'immagine da mostrare (grigia o BGR)
    """
    signal.signal(signal.SIGTERM, _su_sigterm)
    stato = {"esci": False, "lato_x": 0, "larghezza": 0}

    def chiedi_uscita():
        stato["esci"] = True

    def on_mouse(evento, x, y, flags, param):
        if evento == cv2.EVENT_LBUTTONDOWN:
            if x >= stato["larghezza"] - stato["lato_x"] and y <= stato["lato_x"]:
                chiedi_uscita()

    def mostra(img):
        """Mostra un'immagine con la X e gestisce Esc/q. Ritorna True se
        bisogna uscire (X toccata, Esc, giallo)."""
        img = disegna_x(img)
        stato["lato_x"] = _lato_x(img)
        stato["larghezza"] = img.shape[1]
        cv2.imshow(nome_finestra, img)
        if cv2.waitKey(1) & 0xFF in (27, ord('q')):
            stato["esci"] = True
        return stato["esci"]

    def aspetta_uscita(img):
        while not mostra(img):
            time.sleep(0.05)

    _log(f"=== Avvio '{nome_finestra}' (colore={colore}, profondita={profondita}, "
         f"{'solo CPU' if USA_CPU else 'GPU per la profondita'}) ===")

    # 1) Pipeline nel thread principale, PRIMA della finestra (vedi sopra).
    try:
        pipeline, nome_pipeline = _crea_pipeline(profondita)
        errore_pipeline = None
    except Exception as ex:
        pipeline, nome_pipeline, errore_pipeline = None, "", ex
        _log(f"ERRORE libreria Kinect: {ex}")

    # 2) Finestra subito: da qui in poi c'è sempre una X per uscire.
    #    WINDOW_GUI_NORMAL = senza la barra degli strumenti di Qt.
    cv2.namedWindow(nome_finestra, cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL)
    cv2.setWindowProperty(nome_finestra, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(nome_finestra, on_mouse)
    mostra(schermata_messaggio(["Avvio del Kinect v2..."]))

    hardware = _collega_pulsanti(chiedi_uscita)
    device = None
    n_frame = 0
    forza_uscita = False

    try:
        if errore_pipeline is not None:
            aspetta_uscita(schermata_messaggio(
                ["Libreria del Kinect non caricata:", str(errore_pipeline)[:45], "",
                 "Tocca la X per tornare indietro"], (80, 80, 255)))
            return

        # 3) Apertura in un thread a parte: se si blocca (USB appesa), la
        #    finestra resta viva e si può uscire.
        apertura = {}

        def _apri():
            try:
                apertura["ok"] = _apri_kinect(pipeline, nome_pipeline, colore, profondita)
            except Exception as ex:
                apertura["errore"] = ex

        t_apertura = threading.Thread(target=_apri, daemon=True)
        t_apertura.start()
        t0 = time.time()
        while t_apertura.is_alive() and not stato["esci"]:
            mostra(schermata_messaggio([f"Avvio del Kinect v2... {time.time() - t0:.0f} s"]))
            time.sleep(0.05)

        if t_apertura.is_alive():
            _log("Uscita richiesta mentre il Kinect si stava ancora aprendo.")
            forza_uscita = True
            return
        if "ok" in apertura:
            fn, device, listener = apertura["ok"]
        else:
            ex = apertura.get("errore", "errore sconosciuto")
            _log(f"ERRORE apertura: {ex}")
            aspetta_uscita(schermata_messaggio(
                ["Kinect v2 non avviato:", str(ex)[:45], "",
                 "Tocca la X per tornare indietro"], (80, 80, 255)))
            return

        # 4) Ciclo dei frame. Attesa breve (100 ms): se i frame non arrivano,
        #    il ciclo continua a girare e X, Esc e giallo funzionano comunque.
        chiavi = (["color"] if colore else []) + (["ir", "depth"] if profondita else [])
        t_inizio = time.time()
        ultimo_frame = t_inizio
        ultima_stampa = t_inizio

        while not stato["esci"]:
            frames = listener.waitForNewFrame(milliseconds=100)
            ora = time.time()
            if not frames:
                attesa = ora - ultimo_frame
                righe = [f"In attesa delle immagini... {attesa:.0f} s"]
                if attesa > SECONDI_PRIMA_DEL_CONSIGLIO:
                    righe += ["", "Il Kinect non manda immagini.",
                              "Stacca e riattacca l'alimentatore",
                              "del Kinect, poi riapri la camera."]
                if ora - ultima_stampa > 5:
                    _log(f"Nessun frame da {attesa:.0f} s")
                    ultima_stampa = ora
                mostra(schermata_messaggio(righe))
                continue

            try:
                img = elabora({k: frames[k].asarray() for k in chiavi})
            finally:
                listener.release(frames)

            if n_frame == 0:
                _log(f"Primo frame dopo {ora - t_inizio:.1f} s")
            n_frame += 1
            ultimo_frame = ora
            if ora - ultima_stampa > 5:
                _log(f"~{n_frame / (ora - t_inizio):.1f} fps medi")
                ultima_stampa = ora
            mostra(img)

    except KeyboardInterrupt:
        pass
    except Exception as ex:
        _log(f"ERRORE: {ex}")
    finally:
        cv2.destroyAllWindows()
        if hardware:
            import input_fisico
            input_fisico.termina()
        if device is not None and not _chiudi_kinect_con_timeout(device):
            forza_uscita = True
        _log(f"Chiuso dopo {n_frame} frame.")
        if forza_uscita:
            # Un thread USB appeso impedirebbe al processo di terminare:
            # usciamo "di forza", così la GUI torna comunque. Il sistema
            # libera USB e GPIO alla morte del processo.
            os._exit(0)
