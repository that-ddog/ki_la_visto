import sys
import signal

import freenect
import cv2

NOME_FINESTRA = "Normal Camera (debug)"
TIMEOUT_SECONDI = 3  # se una chiamata a freenect impiega più di così, ci fermiamo da soli


class TimeoutFreenect(Exception):
    pass


def _gestore_timeout(signum, frame):
    raise TimeoutFreenect()


signal.signal(signal.SIGALRM, _gestore_timeout)

print("Versione DEBUG: finestra normale (non fullscreen) + diagnostica in console.")
print("Per uscire: ESC nella finestra, oppure Ctrl+C qui nel terminale.")

cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)

contatore = 0
try:
    while True:
        signal.alarm(TIMEOUT_SECONDI)
        try:
            video, timestamp = freenect.sync_get_video()
        except TimeoutFreenect:
            print(f"\n[ERRORE] freenect.sync_get_video() bloccato per più di {TIMEOUT_SECONDI}s.")
            print("Il Kinect non sta restituendo frame video. Possibili cause:")
            print(" - il device è ancora 'occupato' da un processo Kinect precedente non chiuso bene")
            print(" - il driver non riesce a inizializzare lo stream RGB su questo Kinect")
            print(" - problema di connessione USB (il solito adattatore ballerino)")
            break
        finally:
            signal.alarm(0)

        contatore += 1
        if contatore <= 5 or contatore % 60 == 0:
            if video is None:
                print(f"[frame {contatore}] video è None")
            else:
                print(f"[frame {contatore}] shape={video.shape} dtype={video.dtype}")

        if video is None:
            print("Nessun frame ricevuto, esco.")
            break

        video_bgr = cv2.cvtColor(video, cv2.COLOR_RGB2BGR)
        cv2.imshow(NOME_FINESTRA, video_bgr)

        tasto = cv2.waitKey(1) & 0xFF
        if tasto == 27:
            break
except KeyboardInterrupt:
    print("Interrotto da tastiera (Ctrl+C)")

cv2.destroyAllWindows()
sys.exit(0)
