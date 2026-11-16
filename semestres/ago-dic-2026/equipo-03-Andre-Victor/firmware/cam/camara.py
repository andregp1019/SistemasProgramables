# ============================================
# Proyecto:  AuraGuard - Sistema de Seguridad Transportable
# Archivo:   cam/camara.py
# Objetivo:  Inicializar la camara OV2640 (Freenove WROVER o AI-Thinker) y capturar frames JPEG. Se sube a la ESP32-CAM como /camara.py.
# Equipo:    Equipo 03 - Andre (23240369), Victor (23240496)
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================

import time

try:
    import camera
except ImportError:
    camera = None

# Pines de la camara en la placa Freenove ESP32-WROVER CAM (mapa estandar WROVER-KIT).
# OJO: estos GPIO quedan ocupados por la camara y no se pueden usar para sensores.
PINES_FREENOVE = {
    "d0": 4, "d1": 5, "d2": 18, "d3": 19,
    "d4": 36, "d5": 39, "d6": 34, "d7": 35,
    "xclk": 21, "pclk": 22, "vsync": 25, "href": 23,
    "siod": 26, "sioc": 27, "pwdn": -1, "reset": -1,
}

# Pines de la ESP32-CAM AI-Thinker (la placa mas comun), por si tu modulo es de ese tipo.
PINES_AITHINKER = {
    "d0": 5, "d1": 18, "d2": 19, "d3": 21,
    "d4": 36, "d5": 39, "d6": 34, "d7": 35,
    "xclk": 0, "pclk": 22, "vsync": 25, "href": 23,
    "siod": 26, "sioc": 27, "pwdn": 32, "reset": -1,
}


class Camara:
    def __init__(self, framesize="QVGA", calidad=12):
        self.framesize = framesize
        self.calidad = calidad
        self.lista = False
        self.modo_init = None

    def iniciar(self):
        """Prueba varias configuraciones hasta que una funcione. Regresa True/False."""
        if camera is None:
            print("[CAM] No existe el modulo 'camera': el firmware de MicroPython NO tiene soporte de camara.")
            return False

        base = {"format": camera.JPEG}
        con_psram = dict(base)
        if hasattr(camera, "PSRAM"):
            con_psram["fb_location"] = camera.PSRAM

        intentos = [
            ("pines Freenove WROVER + PSRAM", dict(con_psram, **PINES_FREENOVE)),
            ("pines AI-Thinker + PSRAM", dict(con_psram, **PINES_AITHINKER)),
            ("pines por defecto del firmware + PSRAM", con_psram),
            ("pines por defecto, sin PSRAM", base),
        ]
        for nombre, kwargs in intentos:
            try:
                camera.init(0, **kwargs)
                self.lista = True
                self.modo_init = nombre
                print("[CAM] Camara iniciada con:", nombre)
                break
            except Exception as e:
                print("[CAM] Fallo con '%s': %s" % (nombre, e))
                try:
                    camera.deinit()
                except Exception:
                    pass

        if not self.lista:
            return False

        time.sleep_ms(300)  # tiempo de calentamiento del sensor
        try:
            camera.framesize(getattr(camera, "FRAME_" + self.framesize))
        except Exception as e:
            print("[CAM] No se pudo fijar framesize", self.framesize, ":", e)
        try:
            camera.quality(self.calidad)
        except Exception as e:
            print("[CAM] No se pudo fijar la calidad:", e)

        # Los primeros frames suelen salir oscuros o None: se descartan
        for _ in range(3):
            camera.capture()
            time.sleep_ms(100)
        return True

    def capturar(self):
        """Regresa los bytes JPEG del frame, o None si fallo."""
        if not self.lista:
            return None
        for _ in range(3):
            try:
                buf = camera.capture()
                if buf:
                    return buf
            except Exception as e:
                print("[CAM] Error al capturar:", e)
            time.sleep_ms(100)
        return None

    def liberar(self):
        if camera is not None and self.lista:
            try:
                camera.deinit()
            except Exception:
                pass
            self.lista = False
