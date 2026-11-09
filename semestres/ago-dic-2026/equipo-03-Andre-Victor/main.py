#final 
import network
import time
from machine import Pin, PWM, time_pulse_us
from umqtt.simple import MQTTClient

# --- Credenciales ---
SSID = "HolaNoTeConectes"
PASSWORD = "yiyi10196"
MQTT_BROKER = "10.252.118.166" 
CLIENT_ID = "AuraGuard_Sistema_Final_PIR"
MQTT_USER = "admin"
MQTT_PASS = "MiClave2026"
TOPIC_PIR = b"auraguard/sensores/pir"
TOPIC_DIST = b"auraguard/sensores/distancia"
TOPIC_ALERTA = b"auraguard/estado/alerta"

# --- Sensores ---
pir = Pin(13, Pin.IN, Pin.PULL_DOWN)
trigger = Pin(12, Pin.OUT)
echo = Pin(14, Pin.IN)
ir_pin = Pin(19, Pin.IN)  # <-- IR actualizado al pin 19

# --- Actuadores ---
PIN_SERVO = 5             # <-- Servo en el pin 5
servo = PWM(Pin(PIN_SERVO), freq=50)
zumbador = PWM(Pin(15), freq=2000) 
rele = Pin(18, Pin.OUT)   # <-- Relé actualizado al pin 18

zumbador.duty(0)
rele.value(0) 

# --- Variables de estado ---
pir_activado_previo = False
objeto_cerca_previo = False
sistema_armado = True 

# --- Funciones ---
def mover_servo(angulo):
    print(f"-> Moviendo servo a {angulo} grados")
    duty = int(40 + (angulo / 180) * 75)
    servo.duty(duty)

def activar_alarma():
    print("¡Alarma activada!")
    mover_servo(90)     
    zumbador.duty(500)  
    rele.value(1)       
    time.sleep(2)       
    mover_servo(0)      
    zumbador.duty(0)    
    rele.value(0)       

def medir_distancia():
    trigger.value(0)
    time.sleep_us(5)
    trigger.value(1) 
    time.sleep_us(10)
    trigger.value(0)
    try:
        duracion = time_pulse_us(echo, 1, 30000) 
        if duracion <= 0:
            return -1
        return (duracion / 2) / 29.1
    except OSError:
        return -1 

def leer_ir():
    try:
        start_pulse = time_pulse_us(ir_pin, 0, 50000) 
        if start_pulse > 8000:
            codigo = 0
            for _ in range(32):
                time_pulse_us(ir_pin, 0, 5000)
                bit_pulse = time_pulse_us(ir_pin, 1, 5000)
                if bit_pulse < 0:
                    return None
                bit = 1 if bit_pulse > 1000 else 0
                codigo = (codigo << 1) | bit
            return hex(codigo)
    except:
        pass
    return None

def conectar_wifi():
    estacion = network.WLAN(network.STA_IF)
    estacion.active(True)
    if not estacion.isconnected():
        print("Conectando Wi-Fi...")
        estacion.connect(SSID, PASSWORD)
        intentos = 0
        while not estacion.isconnected() and intentos < 10:
            time.sleep(1)
            intentos += 1
        if estacion.isconnected():
            print("WiFi conectado:", estacion.ifconfig()[0])
        else:
            print("Error: No se pudo conectar al WiFi")
    return estacion.isconnected()

# --- Inicio del Programa ---
print("Iniciando sistema...")

if conectar_wifi():
    client = None
    try:
        client = MQTTClient(CLIENT_ID, MQTT_BROKER, user=MQTT_USER, password=MQTT_PASS)
        client.connect()
        print("Conectado al broker MQTT.")
    except Exception as e:
        print("Aviso: Sin conexión MQTT, operando local:", e)
else:
    client = None
    print("Operando sin red.")

print("¡Sistema AuraGuard listo!")
mover_servo(0)
ultimo_tiempo_ultrasonico = time.ticks_ms()

while True:
    try:
        # 1. Control IR
        codigo_recibido = leer_ir()
        if codigo_recibido == '0xffa25d':
            sistema_armado = True
            print(">>> SISTEMA ARMADO <<<")
            zumbador.duty(500)
            time.sleep(0.1)
            zumbador.duty(0)
            if client:
                try: client.publish(TOPIC_ALERTA, b"SISTEMA ARMADO")
                except: pass
                
        elif codigo_recibido == '0xff629d':
            sistema_armado = False
            print(">>> SISTEMA DESARMADO <<<")
            zumbador.duty(500)
            time.sleep(0.1)
            zumbador.duty(0)
            time.sleep(0.1)
            zumbador.duty(500)
            time.sleep(0.1)
            zumbador.duty(0)
            if client:
                try: client.publish(TOPIC_ALERTA, b"SISTEMA DESARMADO")
                except: pass

        # 2. PIR
        estado_pir = pir.value()
        if estado_pir == 1:
            if not pir_activado_previo:
                print("¡Movimiento detectado por PIR!")
                if client:
                    try:
                        client.publish(TOPIC_PIR, b"1")
                        client.publish(TOPIC_ALERTA, b"INTRUSO DETECTADO POR PIR")
                    except: pass
                if sistema_armado:
                    activar_alarma()
                pir_activado_previo = True
        else:
            pir_activado_previo = False
            
        # 3. Ultrasónico
        if time.ticks_diff(time.ticks_ms(), ultimo_tiempo_ultrasonico) > 1000:
            dist = medir_distancia()
            if dist > 0:
                print(f"Distancia: {dist:.1f} cm")
                if client:
                    try: client.publish(TOPIC_DIST, str(round(dist, 1)).encode())
                    except: pass
                
                if dist < 30: 
                    if not objeto_cerca_previo:
                        print("¡Objeto cercano detectado!")
                        if client:
                            try: client.publish(TOPIC_ALERTA, b"ALERTA DE PROXIMIDAD")
                            except: pass
                        if sistema_armado:
                            activar_alarma()
                        objeto_cerca_previo = True
                else:
                    objeto_cerca_previo = False
                    
            ultimo_tiempo_ultrasonico = time.ticks_ms()
            
        time.sleep(0.1)
        
    except Exception as loop_error:
        print("Error en el ciclo:", loop_error)
        time.sleep(1)
