# ============================================
# Proyecto:  AuraGuard - Sistema de Seguridad Transportable
# Archivo:   config.example.py
# Objetivo:  Plantilla de configuracion del servidor de IA. Copiar a config.py; NO subir config.py a GitHub.
# Equipo:    Equipo 03 - Andre (23240369), Victor (23240496)
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================

# ---- Broker Mosquitto (el servidor corre en la MISMA PC del broker) ----
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_USER = "admin"
MQTT_PASS = "TU_CLAVE_MQTT"
CLIENT_ID = "AuraGuard_Servidor_IA"

# ---- Deteccion ----
UMBRAL_DISTANCIA_CM = 30    # mismo valor que firmware/config.py (para etiquetar el disparador)
UMBRAL_CONFIANZA = 0.6      # solo modo SSD (red neuronal). Haar no entrega confianza.
VENTANA = 3                 # se revisan los ultimos N frames...
FRAMES_CONFIRMACION = 2     # ...y se activa la alarma si hay deteccion en al menos M de ellos
COOLDOWN_S = 10             # segundos minimos entre dos alarmas
VERIFICACION_S = 8          # tras un disparo de sensor, tiempo para que la IA confirme

# ---- Formato de frames crudos RGB565 (solo si la camara NO manda JPEG) ----
RGB565_BIG_ENDIAN = True    # si la imagen sale con colores raros/ruido, ponlo en False

# ---- Salida / evidencias ----
MOSTRAR_VENTANA = True      # ventana de OpenCV con el frame procesado (q = salir, s = captura)
GUARDAR_CAPTURAS = True     # guarda frames procesados en servidor/capturas/

# ---- Firebase Realtime Database (Sprint 2: registrar decisiones; deja "" para desactivar) ----
# Ejemplo: "https://auraguard-xxxxx-default-rtdb.firebaseio.com"  (sin "/" al final)
FIREBASE_URL = ""
