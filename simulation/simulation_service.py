import random
import time
from datetime import datetime
import threading
from sensors import sensor_repository
from sensor_logs import sensor_logs_repository

def sensor_readings():
    '''
    Simula la lectura de los sensores activos del sistema. Cada uno devuelve un número entre 0.0 y 1 cada 10 segundos.
    Si se detecta una lectura igual a 1 el sensor es considerado dañado y se imprime una alerta en la terminal.
    '''
    while True:
        sensors = sensor_repository.load_active_sensors()

        for sensor in sensors:
            reading = random.random()

            sensor_logs_repository.create_log(sensor, reading)

            print(f"SENSOR {sensor}: {reading}")

            if reading >= 0.99:
                sensor_repository.mark_as_broken(sensor)
                print(f"SENSOR {sensor} DAÑADO")

        time.sleep(10)

def start_background_tasks():
    thread = threading.Thread(
        target=sensor_readings,
        daemon=True
    )

    thread.start()