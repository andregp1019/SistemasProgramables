# ============================================
# Proyecto:  AuraGuard - Sistema de Seguridad Transportable
# Archivo:   pruebas/test_camara.py
# Objetivo:  Probar la camara de forma aislada: iniciar, capturar y guardar foto.jpg en la placa.
# Equipo:    Equipo 03 - Andre (23240369), Victor (23240496)
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
#
# USO (Thonny): abrir este archivo y presionar Ejecutar (NO hace falta guardarlo en la placa
# si camara.py ya esta en la placa). Si dice "FOTO OK", en el panel de archivos del
# dispositivo aparece foto.jpg: clic derecho -> Descargar a tu PC y abrela.

import time
from camara import Camara

print("Probando camara...")
cam = Camara("QVGA", 12)
if not cam.iniciar():
    print("FALLO: la camara no inicio. Revisa el firmware (debe incluir el modulo 'camera').")
else:
    for i in range(3):
        buf = cam.capturar()
        if buf:
            print("Captura %d OK: %d bytes" % (i + 1, len(buf)))
            with open("foto.jpg", "wb") as f:
                f.write(buf)
        else:
            print("Captura %d: None (reintenta / revisa pines)" % (i + 1))
        time.sleep(1)
    print("FOTO OK -> foto.jpg guardada en la placa (modo: %s)" % cam.modo_init)
    cam.liberar()
