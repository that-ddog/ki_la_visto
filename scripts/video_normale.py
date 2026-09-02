import freenect
import cv2

NOME_FINESTRA = "Normal Camera"

# Immagine RGB "normale" della camera del Kinect (non la depth).
# freenect.sync_get_video() restituisce i pixel in ordine RGB;
# OpenCV si aspetta BGR, quindi convertiamo per avere i colori giusti.

print("Premi ESC nella finestra per uscire")

cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

while True:
    video, _ = freenect.sync_get_video()
    video_bgr = cv2.cvtColor(video, cv2.COLOR_RGB2BGR)
    cv2.imshow(NOME_FINESTRA, video_bgr)
    if cv2.waitKey(1) == 27:
        break

cv2.destroyAllWindows()
