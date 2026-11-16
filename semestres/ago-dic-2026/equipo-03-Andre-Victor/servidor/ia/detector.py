# ============================================
# Proyecto:  AuraGuard - Sistema de Seguridad Transportable
# Archivo:   ia/detector.py
# Objetivo:  Detectar personas (rostros) en un frame con OpenCV: red SSD Caffe si hay modelos, Haar como respaldo.
# Equipo:    Equipo 03 - Andre (23240369), Victor (23240496)
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================

import os

import cv2
import numpy as np

PROTOTXT = "deploy.prototxt"
CAFFEMODEL = "res10_300x300_ssd_iter_140000.caffemodel"


class Detector:
    """Modo 'ssd': red neuronal de la clase (mas precisa, necesita 2 archivos en modelos/).
    Modo 'haar': cascada que ya viene con opencv-python (sin descargas, menos precisa).
    """

    def __init__(self, dir_modelos, umbral=0.6):
        self.umbral = umbral
        self.net = None
        self.cascada = None

        proto = os.path.join(dir_modelos, PROTOTXT)
        modelo = os.path.join(dir_modelos, CAFFEMODEL)
        if os.path.isfile(proto) and os.path.isfile(modelo):
            self.net = cv2.dnn.readNetFromCaffe(proto, modelo)
            self.modo = "ssd"
        else:
            ruta = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
            self.cascada = cv2.CascadeClassifier(ruta)
            if self.cascada.empty():
                raise RuntimeError("No se pudo cargar el haarcascade en: " + ruta)
            self.modo = "haar"

    def detectar(self, img):
        """Regresa una lista de dicts: {'caja': (x1,y1,x2,y2), 'confianza': float|None}."""
        if self.modo == "ssd":
            return self._detectar_ssd(img)
        return self._detectar_haar(img)

    def _detectar_ssd(self, img):
        (h, w) = img.shape[:2]
        blob = cv2.dnn.blobFromImage(img, 1.0, (300, 300), (104.0, 177.0, 123.0))
        self.net.setInput(blob)
        det = self.net.forward()
        resultado = []
        for i in range(det.shape[2]):
            conf = float(det[0, 0, i, 2])
            if conf > self.umbral:
                caja = det[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = caja.astype("int")
                resultado.append({"caja": (int(x1), int(y1), int(x2), int(y2)),
                                  "confianza": round(conf, 3)})
        return resultado

    def _detectar_haar(self, img):
        gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gris = cv2.equalizeHist(gris)
        cajas = self.cascada.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=5,
                                              minSize=(24, 24))
        return [{"caja": (int(x), int(y), int(x + w), int(y + h)), "confianza": None}
                for (x, y, w, h) in cajas]

    def dibujar(self, img, detecciones, texto_extra=""):
        salida = img.copy()
        for d in detecciones:
            x1, y1, x2, y2 = d["caja"]
            cv2.rectangle(salida, (x1, y1), (x2, y2), (0, 255, 0), 2)
            etiqueta = "Persona"
            if d["confianza"] is not None:
                etiqueta += " %.0f%%" % (d["confianza"] * 100)
            cv2.putText(salida, etiqueta, (x1, max(15, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(salida, "%s | %s" % (self.modo.upper(), texto_extra), (5, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        return salida
