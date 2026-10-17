import random
import time
from datetime import datetime
import threading
from sensors import sensor_repository
from sensor_logs import sensor_logs_repository

import json
import os
import pika

def publish_alert(sensor, reading):
    try:
        credentials = pika.PlainCredentials(
            os.getenv("RABBITMQ_USER", "bridgeuser"),
            os.getenv("RABBITMQ_PASSWORD", "bridgepassword")
        )

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
                port=5672,
                credentials=credentials
            )
        )

        channel = connection.channel()

        channel.exchange_declare(
            exchange="sensor_alerts",
            exchange_type="fanout",
            durable=True
        )

        alert = {
            "event": "sensor_damaged",
            "sensor_id": sensor,
            "reading": reading,
            "timestamp": datetime.now().isoformat()
        }

        channel.basic_publish(
            exchange="sensor_alerts",
            routing_key="",
            body=json.dumps(alert),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json"
            )
        )

        connection.close()
        print("Alerta enviada a RabbitMQ:", alert)

    except Exception as error:
        print(f"No se pudo enviar la alerta a RabbitMQ: {error}")

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
                print(' ')
                print(f"SENSOR {sensor} DAÑADO")
                publish_alert(sensor, reading)
                print(' ')

        print(' ')
        time.sleep(10)

def start_background_tasks():
    thread = threading.Thread(
        target=sensor_readings,
        daemon=True
    )

    thread.start()