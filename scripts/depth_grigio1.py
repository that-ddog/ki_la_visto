import freenect
import numpy as np
import cv2

NOME_FINESTRA = "Depth Camera 2"

# Versione "semplice": normalizza ogni frame sul proprio valore massimo,
# senza calibrazione in mm né filtro anti-rumore. È la versione originale
# da cui siamo partiti — tenuta qui apposta per confrontarla con
# depth_grigio1.py.

print("Premi ESC nella finestra per uscire")

cv2.namedWindow(NOME_FINESTRA, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(NOME_FINESTRA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

while True:
    depth, _ = freenect.sync_get_depth()
    depth = depth.astype(np.float32)
    depth = (depth / depth.max()) * 255
    depth = depth.astype(np.uint8)
    cv2.imshow(NOME_FINESTRA, depth)
    if cv2.waitKey(1) == 27:
        break

cv2.destroyAllWindows()
