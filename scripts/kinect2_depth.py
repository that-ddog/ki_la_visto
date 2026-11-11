#!/usr/bin/env python3
"""
kinect2_depth.py
------------------
Kinect v2: SOLO profondità in scala di grigi, a schermo intero.

Rispetto a kinect2_test.py qui la telecamera a colori non viene nemmeno
accesa (startStreams(rgb=False, depth=True)): il Pi non deve più
decomprimere il JPEG 1920x1080 a ogni frame, che era una bella fetta del
lavoro della CPU. Così vediamo quanti fps restano per la sola profondità.

Tasti:  ESC o q = esci     f = schermo intero sì/no
        m = filtro anti-rumore sì/no (vedi quanto costa in fps)

Lancio (dal venv):
    LD_LIBRARY_PATH=$HOME/freenect2/lib python3 kinect2_depth.py         -> profondità calcolata dalla CPU
    LD_LIBRARY_PATH=$HOME/freenect2/lib python3 kinect2_depth.py --gl    -> calcolata dalla GPU (sperimentale)

Con --gl il calcolo della profondità passa alla scheda grafica. I suoi
programmi chiedono OpenGL 3.3, mentre il Pi 5 dichiara 3.1: forziamo il
driver a dichiarare 3.3 (MESA_..._OVERRIDE) e speriamo che regga.
"""

import os
import sys
import time

USA_GL = "--gl" in sys.argv
if USA_GL:
    # Va impostato PRIMA che venga creato il contesto OpenGL.
    os.environ.setdefault("MESA_GL_VERSION_OVERRIDE", "3.3")
    os.environ.setdefault("MESA_GLSL_VERSION_OVERRIDE", "330")

import cv2
import numpy as np

NOME_FINESTRA = "Kinect v2 - profondita'"

# Profondità del Kinect v2: affidabile circa da 0.5 a 4.5 metri.
# Stringi questo intervallo per avere più contrasto sulla zona che ti interessa.
DISTANZA_MIN_MM = 500.0
DISTANZA_MAX_MM = 4500.0

# Filtro mediano (come nel v1): pulisce i puntini, costa un po' di CPU.
DIMENSIONE_FILTRO_RUMORE = 5


def profondita_in_grigio(depth, filtro):
    """mm -> grigio 8 bit: vicino = chiaro, lontano = scuro, niente dato = nero."""
    valida = depth > 0
    clip = np.clip(depth, DISTANZA_MIN_MM, DISTANZA_MAX_MM)
    grigio = 255 - (clip - DISTANZA_MIN_MM) * (255.0 / (DISTANZA_MAX_MM - DISTANZA_MIN_MM))
    grigio = grigio.astype(np.uint8)
    grigio[~valida] = 0
    if filtro and DIMENSIONE_FILTRO_RUMORE > 1:
        grigio = cv2.medianBlur(grigio, DIMENSIONE_FILTRO_RUMORE)
    return grigio


def main():
    from pylibfreenect2 import (Freenect2, SyncMultiFrameListener, FrameType,
                                CpuPacketPipeline, createConsoleLogger,
                                setGlobalLogger, LoggerLevel)

    setGlobalLogger(createConsoleLogger(LoggerLevel.Warning))

    fn = Freenect2()
    if fn.enumerateDevices() == 0:
        print("Nessun Kinect v2 trovato. Controlla: alimentatore acceso, USB nella porta BLU.")
        return
    serial = fn.getDeviceSerialNumber(0)

    pipeline = None
    if USA_GL:
        try:
            from pylibfreenect2 import OpenGLPacketPipeline
            pipeline = OpenGLPacketPipeline()
            nome_pipeline = "GPU (OpenGL)"
        except Exception as ex:
            print(f"Pipeline OpenGL non disponibile ({ex}): uso la CPU.")
    if pipeline is None:
        pipeline = CpuPacketPipeline()
        nome_pipeline = "CPU"
    print(f"Kinect v2 trovato, seriale {serial}. Solo profondità, pipeline {nome_pipeline}...")

    device = fn.openDevice(serial, pipeline=pipeline)
    listener = SyncMultiFrameListener(FrameType.Ir | FrameType.Depth)
    device.setIrAndDepthFrameListener(listener)
    device.startStreams(False, True)  # rgb=False, depth=True

    cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
    schermo_intero = True
    cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    filtro = False  # parte SENZA filtro, per vedere gli fps "puri"
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
                grigio = profondita_in_grigio(frames["depth"].asarray(), filtro)
            finally:
                listener.release(frames)

            ora = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(ora - t_prec, 1e-6))
            t_prec = ora
            n_frame += 1
            if ora - ultima_stampa > 2:
                print(f"[KINECT2] {n_frame} frame, ~{fps:.1f} fps, filtro {'ON' if filtro else 'OFF'}")
                ultima_stampa = ora

            img = cv2.cvtColor(grigio, cv2.COLOR_GRAY2BGR)
            cv2.putText(img, f"{fps:4.1f} fps", (412, 412),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
            cv2.imshow(NOME_FINESTRA, img)

            tasto = cv2.waitKey(1) & 0xFF
            if tasto in (27, ord('q')):
                break
            if tasto == ord('f'):
                schermo_intero = not schermo_intero
                cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN,
                                      cv2.WINDOW_FULLSCREEN if schermo_intero else cv2.WINDOW_NORMAL)
            if tasto == ord('m'):
                filtro = not filtro
                print(f"[KINECT2] filtro anti-rumore {'ON' if filtro else 'OFF'}")
    except KeyboardInterrupt:
        pass
    finally:
        device.stop()
        device.close()
        cv2.destroyAllWindows()
        print(f"Chiuso. Frame totali: {n_frame}")


if __name__ == "__main__":
    main()
