# ============================================
# Proyecto:  AuraGuard - Sistema de Seguridad Transportable
# Archivo:   main.py
# Objetivo:  Firmware ESP32 #1: sensores y actuadores por MQTT; al detectar algo pide una foto a la ESP32-CAM.
# Equipo:    Equipo 03 - Andre (23240369), Victor (23240496)
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================

import gc
import time
import network
import machine
import ubinascii
from umqtt.simple import MQTTClient

import config
from hal.sensores import PIR, Ultrasonico, ReceptorIR
from hal.actuadores import Servo, Zumbador, Rele, Alarma

# ---------------------------------------------------------------- Topicos (HAL)
T_PIR = b"auraguard/sensores/pir"
T_DIST = b"auraguard/sensores/distancia"
T_IR = b"auraguard/sensores/ir"
T_ALERTA = b"auraguard/estado/alerta"
T_SISTEMA = b"auraguard/estado/sistema"
T_ESP32 = b"auraguard/estado/esp32"
T_CAM_CMD = b"auraguard/cam/cmd"   # le pide una foto a la ESP32-CAM

T_CMD_SERVO = b"auraguard/actuadores/servo/cmd"
T_CMD_RELE = b"auraguard/actuadores/rele/cmd"
T_CMD_ZUMBADOR = b"auraguard/actuadores/zumbador/cmd"
T_CMD_ALARMA = b"auraguard/actuadores/alarma/cmd"   # lo publica el servidor de IA
T_CMD_SISTEMA = b"auraguard/sistema/cmd"             # ARMAR / DESARMAR (desde el celular)

T_EST_SERVO = b"auraguard/actuadores/servo/estado"
T_EST_RELE = b"auraguard/actuadores/rele/estado"
T_EST_ZUMBADOR = b"auraguard/actuadores/zumbador/estado"
T_EST_ALARMA = b"auraguard/actuadores/alarma/estado"

SUSCRIPCIONES = (T_CMD_SERVO, T_CMD_RELE, T_CMD_ZUMBADOR, T_CMD_ALARMA, T_CMD_SISTEMA)

# ---------------------------------------------------------------- Estado global
E = {
    "armado": True,
    "pir_prev": 0,
    "cerca_prev": False,
    "t_dist": 0,
    "t_ping": 0,
    "alarma_pedida": False,
    "apagar_pedido": False,
}

cliente = None
pir = ultra = ir = servo = zumbador = rele = alarma = None


# ---------------------------------------------------------------- Red
def conectar_wifi():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if not sta.isconnected():
        print("[WIFI] Conectando a", config.SSID)
        sta.connect(config.SSID, config.PASSWORD)
        intentos = 0
        while not sta.isconnected():
            time.sleep(0.5)
            intentos += 1
            if intentos > 40:
                raise OSError("WiFi timeout: revisa SSID/clave y que la red sea de 2.4 GHz")
    ip = sta.ifconfig()[0]
    print("[WIFI] Conectado. IP:", ip)
    return ip


def conectar_mqtt():
    cid = config.CLIENT_ID + "_" + ubinascii.hexlify(machine.unique_id()).decode()[-4:]
    c = MQTTClient(cid, config.MQTT_BROKER, port=config.MQTT_PORT,
                   user=config.MQTT_USER, password=config.MQTT_PASS, keepalive=60)
    c.set_callback(on_mensaje)
    c.set_last_will(T_ESP32, b"OFFLINE", retain=True)
    c.connect()
    for t in SUSCRIPCIONES:
        c.subscribe(t)
    c.publish(T_ESP32, b"ONLINE", retain=True)
    c.publish(T_SISTEMA, b"ARMADO" if E["armado"] else b"DESARMADO", retain=True)
    print("[MQTT] Conectado a %s:%d como %s" % (config.MQTT_BROKER, config.MQTT_PORT, cid))
    return c


# ---------------------------------------------------------------- Acciones
def cambiar_armado(valor, origen):
    E["armado"] = valor
    if valor:
        print(">>> SISTEMA ARMADO (%s) <<<" % origen)
        zumbador.pitidos(1)
    else:
        print(">>> SISTEMA DESARMADO (%s) <<<" % origen)
        alarma.apagar()
        zumbador.pitidos(2)
    cliente.publish(T_SISTEMA, b"ARMADO" if valor else b"DESARMADO", retain=True)
    cliente.publish(T_ALERTA, b"SISTEMA ARMADO" if valor else b"SISTEMA DESARMADO")


def disparar_alarma(origen):
    alarma.activar()
    print("[ALARMA] Activada por", origen)
    cliente.publish(T_EST_ALARMA, b"ON")
    cliente.publish(T_EST_SERVO, str(servo.angulo).encode())
    cliente.publish(T_EST_RELE, b"1")
    cliente.publish(T_EST_ZUMBADOR, b"1")


def evento(origen):
    """Un sensor detecto algo: avisa y pide una foto a la ESP32-CAM para que la IA decida."""
    print("[EVENTO] Detectado por", origen)
    cliente.publish(T_ALERTA, ("INTRUSO DETECTADO POR " + origen).encode())
    if E["armado"]:
        cliente.publish(T_CAM_CMD, b"FOTO")
        if config.ALARMA_LOCAL:
            disparar_alarma(origen + " (local)")


def on_mensaje(topic, msg):
    """Comandos MQTT -> actuadores (esto cumple 'actuadores respondiendo via MQTT')."""
    try:
        m = msg.decode().strip().upper()
        print("[CMD]", topic.decode(), m)
        if topic == T_CMD_SERVO:
            servo.mover(int(m))
            cliente.publish(T_EST_SERVO, str(servo.angulo).encode())
        elif topic == T_CMD_RELE:
            if m in ("1", "ON"):
                rele.encender()
            else:
                rele.apagar()
            cliente.publish(T_EST_RELE, str(rele.estado).encode())
        elif topic == T_CMD_ZUMBADOR:
            if m in ("1", "ON"):
                zumbador.encender()
            else:
                zumbador.apagar()
            cliente.publish(T_EST_ZUMBADOR, str(zumbador.estado).encode())
        elif topic == T_CMD_ALARMA:
            if m in ("ON", "1"):
                if E["armado"]:
                    E["alarma_pedida"] = True
                else:
                    print("[CMD] Alarma ignorada: sistema desarmado")
            else:
                E["apagar_pedido"] = True
        elif topic == T_CMD_SISTEMA:
            if m in ("ARMAR", "ON", "1"):
                cambiar_armado(True, "MQTT")
            elif m in ("DESARMAR", "OFF", "0"):
                cambiar_armado(False, "MQTT")
    except Exception as e:
        print("[CMD] Error procesando comando:", e)


# ---------------------------------------------------------------- Programa
def iniciar_hardware():
    global pir, ultra, ir, servo, zumbador, rele, alarma
    # Actuadores primero, para dejarlos en estado seguro
    servo = Servo(config.PIN_SERVO)
    zumbador = Zumbador(config.PIN_ZUMBADOR)
    rele = Rele(config.PIN_RELE)
    alarma = Alarma(servo, zumbador, rele, config.DURACION_ALARMA_MS)
    pir = PIR(config.PIN_PIR)
    ultra = Ultrasonico(config.PIN_TRIG, config.PIN_ECHO)
    ir = ReceptorIR(config.PIN_IR)


def main(max_ciclos=None):
    global cliente
    iniciar_hardware()
    conectar_wifi()
    cliente = conectar_mqtt()

    t_inicio = time.ticks_ms()
    print("[SISTEMA] AuraGuard (sensores y actuadores) listo. Calentando PIR %d s..." % config.PIR_CALENTAMIENTO_S)
    fallos = 0
    ciclo = 0

    while True:
        if max_ciclos is not None and ciclo >= max_ciclos:
            break
        ciclo += 1
        try:
            ahora = time.ticks_ms()
            cliente.check_msg()

            # Ordenes recibidas por callback (se ejecutan aqui, en el ciclo principal)
            if E["apagar_pedido"]:
                E["apagar_pedido"] = False
                alarma.apagar()
                cliente.publish(T_EST_ALARMA, b"OFF")
            if E["alarma_pedida"]:
                E["alarma_pedida"] = False
                disparar_alarma("IA (servidor)")

            # 1) Control remoto IR
            codigo = ir.leer()
            if codigo is not None:
                if codigo == config.IR_ARMAR:
                    cambiar_armado(True, "control IR")
                elif codigo == config.IR_DESARMAR:
                    cambiar_armado(False, "control IR")
                else:
                    print("[IR] Codigo sin asignar:", hex(codigo))
                cliente.publish(T_IR, hex(codigo).encode())

            # 2) PIR (se publican los cambios 0->1 y 1->0)
            calentando = time.ticks_diff(ahora, t_inicio) < config.PIR_CALENTAMIENTO_S * 1000
            v = pir.leer()
            if v != E["pir_prev"]:
                E["pir_prev"] = v
                if not calentando:
                    cliente.publish(T_PIR, b"1" if v else b"0")
                    if v == 1:
                        evento("PIR")

            # 3) Ultrasonico (1 lectura por segundo)
            if time.ticks_diff(ahora, E["t_dist"]) >= 1000:
                E["t_dist"] = ahora
                d = ultra.distancia_cm()
                if d > 0:
                    cliente.publish(T_DIST, str(round(d, 1)).encode())
                    cerca = d < config.UMBRAL_DISTANCIA_CM
                    if cerca and not E["cerca_prev"]:
                        evento("ULTRASONICO (%.1f cm)" % d)
                    E["cerca_prev"] = cerca

            # 4) Fin de alarma
            if alarma.actualizar():
                cliente.publish(T_EST_ALARMA, b"OFF")
                cliente.publish(T_EST_SERVO, b"0")
                cliente.publish(T_EST_RELE, b"0")
                cliente.publish(T_EST_ZUMBADOR, b"0")

            # 5) Keepalive
            if time.ticks_diff(ahora, E["t_ping"]) >= 30000:
                E["t_ping"] = ahora
                cliente.ping()

            fallos = 0
            time.sleep_ms(20)

        except Exception as e:
            fallos += 1
            print("[ERR] Ciclo %d (fallo %d): %s" % (ciclo, fallos, e))
            if fallos >= 5:
                print("[ERR] Demasiados fallos seguidos: reiniciando...")
                machine.reset()
            time.sleep(2)
            try:
                sta = network.WLAN(network.STA_IF)
                if not sta.isconnected():
                    conectar_wifi()
                cliente = conectar_mqtt()
            except Exception as e2:
                print("[ERR] Reconexion fallida:", e2)


if __name__ == "__main__":
    main()
