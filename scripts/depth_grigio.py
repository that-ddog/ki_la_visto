import freenect
import numpy as np
import cv2

print("Premi ESC nella finestra per uscire")

while True:
    # leggi un frame di profondità dal Kinect
    depth, _ = freenect.sync_get_depth()

    # depth e' una matrice di distanze (uint16, in mm), valori 0-2047 sul v1
    # la normalizziamo in scala 0-255 per poterla vedere in grigio
    depth = depth.astype(np.float32)
    depth = (depth / depth.max()) * 255
    depth = depth.astype(np.uint8)

    # mostra a schermo
    cv2.imshow("Depth Grigio", depth)

    # esci con ESC
    if cv2.waitKey(1) == 27:
        break

cv2.destroyAllWindows()
