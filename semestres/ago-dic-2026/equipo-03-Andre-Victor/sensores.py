# ============================================
# Proyecto:  AuraGuard - Sistema de Seguridad Transportable
# Archivo:   hal/sensores.py
# Objetivo:  HAL de sensores: PIR, ultrasonico HC-SR04 y receptor IR (protocolo NEC).
# Equipo:    Equipo 03 - Andre (23240369), Victor (23240496)
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================

from machine import Pin, time_pulse_us
import time


class PIR:
    """Sensor de movimiento HC-SR501. 1 = movimiento, 0 = reposo."""

    def __init__(self, pin):
        # PULL_DOWN fuerza el estado base en 0 (evita lecturas flotantes)
        self.pin = Pin(pin, Pin.IN, Pin.PULL_DOWN)

    def leer(self):
        return self.pin.value()


class Ultrasonico:
    """HC-SR04. Devuelve centimetros, o -1 si no hubo eco."""

    def __init__(self, pin_trig, pin_echo):
        self.trig = Pin(pin_trig, Pin.OUT)
        self.echo = Pin(pin_echo, Pin.IN)
        self.trig.value(0)

    def distancia_cm(self):
        self.trig.value(0)
        time.sleep_us(5)
        self.trig.value(1)
        time.sleep_us(10)
        self.trig.value(0)
        try:
            duracion = time_pulse_us(self.echo, 1, 30000)
        except OSError:
            return -1
        if duracion <= 0:
            return -1
        return (duracion / 2) / 29.1


class ReceptorIR:
    """Receptor VS1838B con decodificacion NEC usando time_pulse_us.

    leer() espera hasta 50 ms por el pulso de inicio. Si no llega nada
    regresa None; si llega una trama valida regresa el codigo (int).
    """

    def __init__(self, pin):
        self.pin = Pin(pin, Pin.IN)

    def leer(self):
        try:
            inicio = time_pulse_us(self.pin, 0, 50000)
            if inicio > 8000:
                codigo = 0
                for _ in range(32):
                    time_pulse_us(self.pin, 0, 5000)
                    alto = time_pulse_us(self.pin, 1, 5000)
                    if alto < 0:
                        return None
                    bit = 1 if alto > 1000 else 0
                    codigo = (codigo << 1) | bit
                return codigo
        except Exception:
            pass
        return None
