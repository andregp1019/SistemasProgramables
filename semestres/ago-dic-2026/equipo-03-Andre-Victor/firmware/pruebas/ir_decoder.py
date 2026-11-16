# ============================================
# Proyecto:  AuraGuard - Sistema de Seguridad Transportable
# Archivo:   pruebas/ir_decoder.py
# Objetivo:  Mostrar el codigo HEX de cada boton del control remoto (protocolo NEC) para usarlos en config.py.
# Equipo:    Equipo 03 - Andre (23240369), Victor (23240496)
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
#
# USO: ejecutar en Thonny, apuntar el control al receptor y presionar botones.
# Copia los codigos que quieras a IR_ARMAR / IR_DESARMAR en config.py.
# Cambia PIN_IR_PRUEBA al pin donde conectaste TU receptor (S/OUT).

import time
from hal.sensores import ReceptorIR

PIN_IR_PRUEBA = 19   # pin del receptor IR en la ESP32 #1 (el mismo que PIN_IR de config.py)

receptor = ReceptorIR(PIN_IR_PRUEBA)
print("Decodificador IR activo en GPIO", PIN_IR_PRUEBA)
print("Apunta tu control y presiona un boton...")

while True:
    codigo = receptor.leer()
    if codigo is not None:
        print("Boton detectado -> codigo HEX:", hex(codigo))
        time.sleep_ms(300)
