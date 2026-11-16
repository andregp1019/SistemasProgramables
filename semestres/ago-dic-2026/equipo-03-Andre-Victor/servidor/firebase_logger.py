# ============================================
# Proyecto:  AuraGuard - Sistema de Seguridad Transportable
# Archivo:   firebase_logger.py
# Objetivo:  Registrar cada decision de la IA en Firebase Realtime Database (REST) sin bloquear el servidor.
# Equipo:    Equipo 03 - Andre (23240369), Victor (23240496)
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================

import queue
import threading

try:
    import requests
except ImportError:  # sin requests el logger se desactiva solo
    requests = None


class FirebaseLogger:
    """Envia datos en un hilo aparte. Si FIREBASE_URL esta vacio, no hace nada."""

    def __init__(self, base_url):
        self.url = (base_url or "").rstrip("/")
        self.activo = bool(self.url) and requests is not None
        self._cola = queue.Queue(maxsize=200)
        if self.url and requests is None:
            print("[FIREBASE] Falta 'requests' (pip install requests): logger desactivado")
        if self.activo:
            threading.Thread(target=self._trabajador, daemon=True).start()
            print("[FIREBASE] Registro activo en", self.url)
        else:
            print("[FIREBASE] Desactivado (FIREBASE_URL vacio)")

    def registrar_evento(self, clave, datos):
        """PUT /eventos_ia/{clave}.json  (clave = timestamp en ms)."""
        self._encolar("PUT", "/eventos_ia/%s.json" % clave, datos)

    def actualizar_estado(self, datos):
        """PATCH /estado_actual.json (solo cambia los campos enviados)."""
        self._encolar("PATCH", "/estado_actual.json", datos)

    def _encolar(self, metodo, ruta, datos):
        if not self.activo:
            return
        try:
            self._cola.put_nowait((metodo, self.url + ruta, datos))
        except queue.Full:
            print("[FIREBASE] Cola llena: dato descartado")

    def _trabajador(self):
        while True:
            metodo, url, datos = self._cola.get()
            try:
                r = requests.request(metodo, url, json=datos, timeout=6)
                if r.status_code >= 300:
                    print("[FIREBASE] HTTP %d en %s (revisa reglas y que la URL sea la de RTDB)"
                          % (r.status_code, url))
            except Exception as e:
                print("[FIREBASE] Error de red:", e)
