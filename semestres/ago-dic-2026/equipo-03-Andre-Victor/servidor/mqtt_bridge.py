# ============================================
# Proyecto:  AuraGuard - Sistema de Seguridad Transportable
# Archivo:   mqtt_bridge.py
# Objetivo:  Servidor de IA: recibe frames por MQTT, detecta personas con OpenCV y publica la orden al actuador.
# Equipo:    Equipo 03 - Andre (23240369), Victor (23240496)
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
#
# Flujo:  ESP32-CAM --(auraguard/cam/frame)--> este script --> OpenCV/IA
#         --> (auraguard/actuadores/alarma/cmd = ON) --> ESP32 activa servo + zumbador + rele
#
# Uso:    python mqtt_bridge.py      (en la misma PC donde corre Mosquitto)

import json
import os
import queue
import sys
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np
import paho.mqtt.client as mqtt

import config
from firebase_logger import FirebaseLogger
from ia.detector import Detector

try:  # consola de Windows: evita errores con acentos
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
DIR_MODELOS = os.path.join(BASE, "modelos")
DIR_CAPTURAS = os.path.join(BASE, "capturas")
DIR_LOGS = os.path.join(BASE, "logs")

T_FRAME = "auraguard/cam/frame"
T_PIR = "auraguard/sensores/pir"
T_DIST = "auraguard/sensores/distancia"
T_SISTEMA = "auraguard/estado/sistema"
T_ESP32 = "auraguard/estado/esp32"
T_CAM_ESTADO = "auraguard/estado/cam"
T_CMD_ALARMA = "auraguard/actuadores/alarma/cmd"
T_DECISION = "auraguard/ia/decision"

UMBRAL_DIST = getattr(config, "UMBRAL_DISTANCIA_CM", 30)

frames = queue.Queue(maxsize=2)  # solo se conservan los frames mas recientes
ctx = {"pir": 0, "dist": None, "armado": True, "trigger": None, "esp32": "?"}


# ------------------------------------------------------------------ utilidades
def log(msg):
    linea = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg)
    print(linea, flush=True)
    try:
        with open(os.path.join(DIR_LOGS, "decisiones.log"), "a", encoding="utf-8") as f:
            f.write(datetime.now().strftime("%Y-%m-%d ") + linea + "\n")
    except OSError:
        pass


def crear_cliente():
    try:  # paho-mqtt >= 2.0
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=config.CLIENT_ID)
    except AttributeError:  # paho-mqtt 1.x
        return mqtt.Client(client_id=config.CLIENT_ID)


# Tamanos tipicos de frames crudos RGB565 (2 bytes por pixel) -> (ancho, alto)
TAMANOS_RAW = {38400: (160, 120), 115200: (240, 240), 153600: (320, 240), 614400: (640, 480)}


def decodificar_frame(datos):
    """Acepta JPEG (lo normal) o RGB565 crudo (lo que manda tu camara ahora). Regresa BGR o None."""
    if datos[:2] == b"\xff\xd8":
        return cv2.imdecode(np.frombuffer(datos, dtype=np.uint8), cv2.IMREAD_COLOR)
    medidas = TAMANOS_RAW.get(len(datos))
    if medidas is None:
        return None
    ancho, alto = medidas
    a = np.frombuffer(datos, dtype=np.uint8).reshape(alto, ancho, 2)
    if getattr(config, "RGB565_BIG_ENDIAN", True):
        a = a[:, :, ::-1]  # la camara manda primero el byte alto
    return cv2.cvtColor(np.ascontiguousarray(a), cv2.COLOR_BGR5652BGR)


# ------------------------------------------------------------------ callbacks MQTT
def on_connect(client, userdata, flags, rc, *extra):
    if rc == 0 or "success" in str(rc).lower():
        log("[MQTT] Conectado al broker %s:%s" % (config.MQTT_HOST, config.MQTT_PORT))
        client.subscribe([(T_FRAME, 0), (T_PIR, 0), (T_DIST, 0), (T_SISTEMA, 0), (T_ESP32, 0), (T_CAM_ESTADO, 0)])
    else:
        log("[MQTT] Conexion rechazada (%s). Revisa usuario/clave de Mosquitto." % rc)


def on_message(client, userdata, msg):
    t, p = msg.topic, msg.payload
    if t == T_FRAME:
        item = (time.time(), bytes(p))
        try:
            frames.put_nowait(item)
        except queue.Full:  # descarta el mas viejo y deja el nuevo
            try:
                frames.get_nowait()
                frames.put_nowait(item)
            except (queue.Empty, queue.Full):
                pass
    elif t == T_PIR:
        ctx["pir"] = 1 if p.strip() == b"1" else 0
        if ctx["pir"] == 1:
            ctx["trigger"] = (time.time(), "PIR")
    elif t == T_DIST:
        try:
            d = float(p)
        except ValueError:
            return
        previa = ctx["dist"]
        ctx["dist"] = d
        if d < UMBRAL_DIST and (previa is None or previa >= UMBRAL_DIST):
            ctx["trigger"] = (time.time(), "ULTRASONICO")
    elif t == T_SISTEMA:
        ctx["armado"] = p.strip() == b"ARMADO"
        if not ctx["armado"]:
            ctx["trigger"] = None
        log("[ESTADO] Sistema %s" % p.decode(errors="replace"))
    elif t == T_CAM_ESTADO:
        log("[ESTADO] ESP32-CAM %s" % p.decode(errors="replace"))
    elif t == T_ESP32:
        ctx["esp32"] = p.decode(errors="replace")
        log("[ESTADO] ESP32 %s" % ctx["esp32"])


# ------------------------------------------------------------------ programa
def main():
    for d in (DIR_CAPTURAS, DIR_LOGS):
        os.makedirs(d, exist_ok=True)

    detector = Detector(DIR_MODELOS, config.UMBRAL_CONFIANZA)
    log("[IA] Detector en modo '%s'%s" % (
        detector.modo,
        "" if detector.modo == "ssd" else "  (para mayor precision copia los modelos SSD en servidor/modelos/)"))
    fb = FirebaseLogger(config.FIREBASE_URL)

    cliente = crear_cliente()
    cliente.username_pw_set(config.MQTT_USER, config.MQTT_PASS)
    cliente.on_connect = on_connect
    cliente.on_message = on_message
    cliente.reconnect_delay_set(1, 30)
    try:
        cliente.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=60)
    except Exception as e:
        log("[MQTT] No se pudo conectar: %s. ¿Mosquitto esta corriendo? ¿host/puerto correctos?" % e)
        return
    cliente.loop_start()

    historial = deque(maxlen=config.VENTANA)
    ultima_alarma = 0.0
    mostrar = config.MOSTRAR_VENTANA
    n_frames = 0
    log("[SISTEMA] Servidor de IA listo. Esperando frames en '%s'  (q = salir, s = captura)" % T_FRAME)

    try:
        while True:
            try:
                ts, jpg = frames.get(timeout=0.2)
            except queue.Empty:
                if mostrar and (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break
                continue

            img = decodificar_frame(jpg)
            if img is None:
                log("[FRAME] Formato no reconocido (%d bytes): se ignora" % len(jpg))
                continue
            n_frames += 1
            alto, ancho = img.shape[:2]

            t0 = time.time()
            dets = detector.detectar(img)
            ms_ia = (time.time() - t0) * 1000.0
            log("[FRAME] #%d %dx%d %.1f KB -> [IA] %d persona(s) (%s, %.0f ms)"
                % (n_frames, ancho, alto, len(jpg) / 1024.0, len(dets), detector.modo, ms_ia))

            historial.append(1 if dets else 0)
            confirmado = sum(historial) >= config.FRAMES_CONFIRMACION
            ahora = time.time()
            trig = ctx["trigger"]
            if trig and ahora - trig[0] > config.VERIFICACION_S:
                disparador_activo = False
            else:
                disparador_activo = trig is not None
            disparador = trig[1] if disparador_activo else "PATRULLA"
            anotado = detector.dibujar(img, dets, "armado" if ctx["armado"] else "DESARMADO")

            if confirmado and ctx["armado"] and ahora - ultima_alarma >= config.COOLDOWN_S:
                ultima_alarma = ahora
                confs = [d["confianza"] for d in dets if d["confianza"] is not None]
                registro = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "deteccion": "persona",
                    "accion": "alarma_ON",
                    "confianza": max(confs) if confs else None,
                    "n_detecciones": len(dets),
                    "disparador": disparador,
                    "modo_detector": detector.modo,
                    "distancia_cm": ctx["dist"],
                    "pir": ctx["pir"],
                }
                cliente.publish(T_CMD_ALARMA, "ON")
                cliente.publish(T_DECISION, json.dumps(registro))
                log("[ACTUADOR] IA detecta persona (disparador: %s) -> publico %s = ON  => alarma activada"
                    % (disparador, T_CMD_ALARMA))
                fb.registrar_evento(int(ahora * 1000), {k: v for k, v in registro.items() if v is not None})
                fb.actualizar_estado({"ia_ultima_decision": "alarma_ON", "ia_timestamp": registro["timestamp"]})
                if config.GUARDAR_CAPTURAS:
                    ruta = os.path.join(DIR_CAPTURAS, "alarma_%s.jpg" % datetime.now().strftime("%Y%m%d_%H%M%S"))
                    cv2.imwrite(ruta, anotado)
                    log("[CAPTURA] Guardada: %s" % ruta)
                ctx["trigger"] = None
                historial.clear()
            elif confirmado and not ctx["armado"]:
                log("[IA] Persona detectada pero el sistema esta DESARMADO: sin accion")
            elif trig and not dets and not disparador_activo:
                registro = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "deteccion": "ninguna",
                    "accion": "descartado_sin_persona",
                    "disparador": trig[1],
                    "modo_detector": detector.modo,
                }
                log("[IA] Disparo de %s sin persona en camara: falsa alarma DESCARTADA" % trig[1])
                cliente.publish(T_DECISION, json.dumps(registro))
                fb.registrar_evento(int(ahora * 1000), registro)
                ctx["trigger"] = None

            if mostrar:
                try:
                    cv2.imshow("AuraGuard IA", anotado)
                    tecla = cv2.waitKey(1) & 0xFF
                    if tecla == ord("q"):
                        break
                    if tecla == ord("s"):
                        ruta = os.path.join(DIR_CAPTURAS, "manual_%s.jpg" % datetime.now().strftime("%Y%m%d_%H%M%S"))
                        cv2.imwrite(ruta, anotado)
                        log("[CAPTURA] Guardada: %s" % ruta)
                except cv2.error:
                    log("[AVISO] Tu OpenCV no puede abrir ventanas (¿opencv-python-headless?). Sigo sin ventana.")
                    mostrar = False
    except KeyboardInterrupt:
        pass
    finally:
        log("[SISTEMA] Cerrando servidor...")
        cliente.loop_stop()
        cliente.disconnect()
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass


if __name__ == "__main__":
    main()
