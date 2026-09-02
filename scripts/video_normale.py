import sys
import signal

import freenect
import cv2
import tkinter as tk

NOME_FINESTRA = "Normal Camera"
TIMEOUT_SECONDI = 3  # se una chiamata freenect impiega più di così, ci fermiamo da soli


class TimeoutFreenect(Exception):
    pass


def _gestore_timeout(signum, frame):
    raise TimeoutFreenect()


signal.signal(signal.SIGALRM, _gestore_timeout)

# Misuriamo la risoluzione dello schermo con un Tk "usa e getta", ed evitiamo
# la modalità fullscreen ESCLUSIVA di OpenCV (WND_PROP_FULLSCREEN): su questo
# sistema, con backend Qt sotto un ambiente che prova Wayland, quella
# modalità può bloccare la finestra e non rispondere più a nulla (come hai
# visto). Una finestra normale ridimensionata a schermo intero è quasi
# identica visivamente, ma resta sempre "viva" e ha i bordi di sistema come
# rete di sicurezza in più.
_tmp = tk.Tk()
LARGHEZZA_SCHERMO = _tmp.winfo_screenwidth()
ALTEZZA_SCHERMO = _tmp.winfo_screenheight()
_tmp.destroy()

print("Premi ESC nella finestra per uscire")

cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
cv2.resizeWindow(NOME_FINESTRA, LARGHEZZA_SCHERMO, ALTEZZA_SCHERMO)
cv2.moveWindow(NOME_FINESTRA, 0, 0)

try:
    while True:
        signal.alarm(TIMEOUT_SECONDI)
        try:
            video, timestamp = freenect.sync_get_video()
        except TimeoutFreenect:
            print(f"[ERRORE] freenect.sync_get_video() bloccato per più di {TIMEOUT_SECONDI}s, esco.")
            break
        finally:
            signal.alarm(0)

        if video is None:
            print("Nessun frame ricevuto, esco.")
            break

        video_bgr = cv2.cvtColor(video, cv2.COLOR_RGB2BGR)
        cv2.imshow(NOME_FINESTRA, video_bgr)

        if cv2.waitKey(1) & 0xFF == 27:
            break
except KeyboardInterrupt:
    pass

cv2.destroyAllWindows()
sys.exit(0)
