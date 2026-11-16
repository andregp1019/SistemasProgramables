# ============================================
# Proyecto:  AuraGuard - Sistema de Seguridad Transportable
# Archivo:   hal/actuadores.py
# Objetivo:  HAL de actuadores: servo, zumbador pasivo, rele y alarma combinada no bloqueante.
# Equipo:    Equipo 03 - Andre (23240369), Victor (23240496)
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================

from machine import Pin, PWM
import time


def _duty(pwm, valor_0_1023):
    """Compatibilidad entre versiones de MicroPython (duty / duty_u16)."""
    try:
        pwm.duty(valor_0_1023)
    except AttributeError:
        pwm.duty_u16(valor_0_1023 * 64)


class Servo:
    """SG90 a 50 Hz. 0 = barrera en reposo, 90 = barrera activada (alarma)."""

    def __init__(self, pin):
        self.pwm = PWM(Pin(pin), freq=50)
        self.angulo = 0
        self.mover(0)

    def mover(self, angulo):
        angulo = max(0, min(180, int(angulo)))
        _duty(self.pwm, int(40 + (angulo / 180) * 75))
        self.angulo = angulo


class Zumbador:
    """Zumbador PASIVO: necesita PWM (2000 Hz) para sonar."""

    def __init__(self, pin, freq=2000):
        self.pwm = PWM(Pin(pin), freq=freq)
        self.estado = 0
        self.apagar()

    def encender(self):
        _duty(self.pwm, 500)
        self.estado = 1

    def apagar(self):
        _duty(self.pwm, 0)
        self.estado = 0

    def pitidos(self, n, ms=100):
        for _ in range(n):
            self.encender()
            time.sleep_ms(ms)
            self.apagar()
            time.sleep_ms(ms)


class Rele:
    """Modulo rele (luz). Con el modulo de tu amigo, value(1) = activo."""

    def __init__(self, pin):
        self.pin = Pin(pin, Pin.OUT)
        self.estado = 0
        self.apagar()

    def encender(self):
        self.pin.value(1)
        self.estado = 1

    def apagar(self):
        self.pin.value(0)
        self.estado = 0


class Alarma:
    """Servo + zumbador + rele juntos, SIN time.sleep (no congela el ciclo principal)."""

    def __init__(self, servo, zumbador, rele, duracion_ms=2000):
        self.servo = servo
        self.zumbador = zumbador
        self.rele = rele
        self.duracion_ms = duracion_ms
        self.activa = False
        self._fin = 0

    def activar(self):
        self.servo.mover(90)
        self.zumbador.encender()
        self.rele.encender()
        self.activa = True
        self._fin = time.ticks_add(time.ticks_ms(), self.duracion_ms)

    def apagar(self):
        self.servo.mover(0)
        self.zumbador.apagar()
        self.rele.apagar()
        self.activa = False

    def actualizar(self):
        """Llamar en cada ciclo. Regresa True en el instante en que se apaga."""
        if self.activa and time.ticks_diff(time.ticks_ms(), self._fin) >= 0:
            self.apagar()
            return True
        return False
