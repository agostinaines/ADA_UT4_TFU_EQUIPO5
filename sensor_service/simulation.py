"""
Simulación de sensores: cada CYCLE_SECONDS genera una lectura entre 0.0 y 1.0 por sensor activo
y la procesa igual que si el sensor la hubiera enviado por POST /readings.
"""
import os
import random
import threading
import time
from datetime import datetime

import readings
import repository

CYCLE_SECONDS = int(os.getenv("READING_INTERVAL_SECONDS", "10"))

_state = {"last_cycle": None}
_thread = None


def sensor_readings():
    while True:
        try:
            for sensor in repository.load_active_sensors():
                reading = random.random()
                print(f"SENSOR {sensor['id']}: {reading}", flush=True)
                readings.process_reading(sensor["id"], reading)

            _state["last_cycle"] = datetime.now().isoformat()
            print(" ", flush=True)
        except Exception as error:
            print(f"[sensor-service] error en el ciclo de lecturas: {error}", flush=True)
        time.sleep(CYCLE_SECONDS)


def start_background_tasks():
    global _thread
    _thread = threading.Thread(target=sensor_readings, daemon=True)
    _thread.start()


def status():
    return {
        "activa": bool(_thread and _thread.is_alive()),
        "ultimo_ciclo": _state["last_cycle"],
    }
