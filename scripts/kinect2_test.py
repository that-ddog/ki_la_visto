#!/usr/bin/env python3
"""
kinect2_test.py
-----------------
Primo test del Kinect v2 sul Pi 5, stile primo test del Kinect v1:
apre il sensore e mostra in UNA finestra OpenCV quattro riquadri:

    +----------------------+----------------------+
    | COLORE (1080p)       | INFRAROSSI           |
    +----------------------+----------------------+
    | PROFONDITA' grigio   | PROFONDITA' colori   |
    +----------------------+----------------------+

Niente OpenGL (che sul Pi 5 dava la finestra nera di Protonect): la
profondità la calcola la CPU, e il disegno lo fa OpenCV come per il v1.

Tasti:  ESC o q = esci     f = schermo intero sì/no     1/2/3/4 = solo un
riquadro a tutto schermo     0 = torna alla griglia

Lancio (dal venv):
    LD_LIBRARY_PATH=$HOME/freenect2/lib python3 kinect2_test.py
"""

import time

import cv2
import numpy as np

NOME_FINESTRA = "Kinect v2 - test"

# Profondità del Kinect v2: affidabile circa da 0.5 a 4.5 metri.
DISTANZA_MIN_MM = 500.0
DISTANZA_MAX_MM = 4500.0

# Infrarossi: valori grezzi fino a 65535, ma la scena di solito sta molto
# più in basso. Questo è il valore che diventa "bianco": abbassalo se
# l'immagine IR è troppo scura, alzalo se è bruciata.
IR_BIANCO = 20000.0

CELLA_W, CELLA_H = 512, 424  # risoluzione nativa di IR e profondità


def colore_in_cella(bgrx):
    """Colore 1920x1080 (BGRX) -> 512x424 senza deformarlo (bande nere sopra/sotto)."""
    bgr = bgrx[:, :, :3]
    h = int(round(CELLA_W * bgr.shape[0] / bgr.shape[1]))  # 288
    piccolo = cv2.resize(bgr, (CELLA_W, h), interpolation=cv2.INTER_AREA)
    cella = np.zeros((CELLA_H, CELLA_W, 3), np.uint8)
    y0 = (CELLA_H - h) // 2
    cella[y0:y0 + h] = piccolo
    return cella


def ir_in_grigio(ir):
    """Infrarossi (float, 0..65535) -> grigio 8 bit, con radice quadrata per
    schiarire le zone scure (l'IR attivo ha molta dinamica)."""
    norm = np.clip(ir / IR_BIANCO, 0.0, 1.0)
    return (np.sqrt(norm) * 255).astype(np.uint8)


def profondita_in_grigio(depth):
    """Profondità in mm -> grigio: vicino = chiaro, lontano = scuro, niente dato = nero."""
    valida = depth > 0
    clip = np.clip(depth, DISTANZA_MIN_MM, DISTANZA_MAX_MM)
    grigio = 255 - (clip - DISTANZA_MIN_MM) / (DISTANZA_MAX_MM - DISTANZA_MIN_MM) * 255
    grigio = grigio.astype(np.uint8)
    grigio[~valida] = 0
    return grigio


def profondita_a_colori(grigio):
    colorata = cv2.applyColorMap(grigio, cv2.COLORMAP_TURBO)
    colorata[grigio == 0] = 0
    return colorata


def etichetta(img, testo):
    cv2.putText(img, testo, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, testo, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    return img


def componi(color, ir, depth, fps, vista):
    celle = [
        etichetta(colore_in_cella(color), "COLORE"),
        etichetta(cv2.cvtColor(ir_in_grigio(ir), cv2.COLOR_GRAY2BGR), "INFRAROSSI"),
    ]
    grigio = profondita_in_grigio(depth)
    celle.append(etichetta(cv2.cvtColor(grigio, cv2.COLOR_GRAY2BGR), "PROFONDITA'"))
    celle.append(etichetta(profondita_a_colori(grigio), "PROFONDITA' TURBO"))

    if vista in (1, 2, 3, 4):
        img = celle[vista - 1]
    else:
        img = np.vstack([np.hstack(celle[:2]), np.hstack(celle[2:])])

    testo = f"{fps:4.1f} fps"
    cv2.putText(img, testo, (img.shape[1] - 140, img.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
    return img


def main():
    from pylibfreenect2 import (Freenect2, SyncMultiFrameListener, FrameType,
                                CpuPacketPipeline, createConsoleLogger,
                                setGlobalLogger, LoggerLevel)

    setGlobalLogger(createConsoleLogger(LoggerLevel.Warning))

    fn = Freenect2()
    if fn.enumerateDevices() == 0:
        print("Nessun Kinect v2 trovato. Controlla: alimentatore acceso, USB nella porta BLU, regola udev.")
        return
    serial = fn.getDeviceSerialNumber(0)
    print(f"Kinect v2 trovato, seriale {serial}. Avvio (pipeline CPU)...")

    device = fn.openDevice(serial, pipeline=CpuPacketPipeline())
    listener = SyncMultiFrameListener(FrameType.Color | FrameType.Ir | FrameType.Depth)
    device.setColorFrameListener(listener)
    device.setIrAndDepthFrameListener(listener)
    device.start()

    cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
    schermo_intero = True
    cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    vista = 0
    fps = 0.0
    t_prec = time.time()
    n_frame = 0
    ultima_stampa = time.time()

    try:
        while True:
            frames = listener.waitForNewFrame(milliseconds=5000)
            if not frames:
                print("Nessun frame da 5 secondi (problema USB?). Riprovo...")
                continue
            try:
                img = componi(frames["color"].asarray(), frames["ir"].asarray(),
                              frames["depth"].asarray(), fps, vista)
            finally:
                listener.release(frames)

            ora = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(ora - t_prec, 1e-6))
            t_prec = ora
            n_frame += 1
            if ora - ultima_stampa > 2:
                print(f"[KINECT2] {n_frame} frame ricevuti, ~{fps:.1f} fps")
                ultima_stampa = ora

            cv2.imshow(NOME_FINESTRA, img)
            tasto = cv2.waitKey(1) & 0xFF
            if tasto in (27, ord('q')):
                break
            if tasto == ord('f'):
                schermo_intero = not schermo_intero
                cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN,
                                      cv2.WINDOW_FULLSCREEN if schermo_intero else cv2.WINDOW_NORMAL)
            if tasto in tuple(ord(str(n)) for n in range(0, 5)):
                vista = tasto - ord('0')
    except KeyboardInterrupt:
        pass
    finally:
        device.stop()
        device.close()
        cv2.destroyAllWindows()
        print(f"Chiuso. Frame totali: {n_frame}")


if __name__ == "__main__":
    main()
