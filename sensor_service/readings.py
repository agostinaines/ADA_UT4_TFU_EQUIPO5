"""
Procesamiento de lecturas del Sensor Service (pasos 1 a 3 del diagrama de secuencia).

  1. Llega una lectura (POST /readings o la simulación).
  2. Se detecta si es una anomalía (lectura >= DAMAGE_THRESHOLD => sensor dañado).
  3. Se publica el evento 'sensor_damaged' en RabbitMQ (AMQP, exchange fanout 'sensor_alerts').
     Desde ahí sigue: Messaging Bridge -> Redis Streams -> Alert Service.

Si hay anomalía, el sensor se marca como roto en la base propia (sensor_db) y se registra la
alerta en estado 'pendiente'; el Alert Service la confirma después (paso 8).
"""
import json
import os
import time
from datetime import datetime

import pika

import repository

DAMAGE_THRESHOLD = float(os.getenv("DAMAGE_THRESHOLD", "0.99"))
PUBLISH_ATTEMPTS = int(os.getenv("PUBLISH_ATTEMPTS", "3"))
PUBLISH_BACKOFF = float(os.getenv("PUBLISH_BACKOFF", "0.5"))
EXCHANGE = "sensor_alerts"


def _publish_once(alert):
    credentials = pika.PlainCredentials(
        os.getenv("RABBITMQ_USER", "bridgeuser"),
        os.getenv("RABBITMQ_PASSWORD", "bridgepassword"),
    )
    params = pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
        port=5672,
        credentials=credentials,
        socket_timeout=3,
        connection_attempts=1,
    )
    connection = pika.BlockingConnection(params)
    try:
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE, exchange_type="fanout", durable=True)
        channel.basic_publish(
            exchange=EXCHANGE,
            routing_key="",
            body=json.dumps(alert),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
    finally:
        connection.close()


def publish_alert(alert):
    """Publica el evento con reintentos acotados. Devuelve True si se pudo publicar."""
    for attempt in range(PUBLISH_ATTEMPTS):
        try:
            _publish_once(alert)
            print("Alerta enviada a RabbitMQ:", alert, flush=True)
            return True
        except Exception as error:
            print(f"[sensor-service] No se pudo publicar la alerta (intento {attempt + 1}/"
                  f"{PUBLISH_ATTEMPTS}): {error}", flush=True)
            if attempt < PUBLISH_ATTEMPTS - 1:
                time.sleep(PUBLISH_BACKOFF * (2 ** attempt))
    return False


def process_reading(sensor_id, reading):
    """Guarda la lectura, detecta anomalías y publica el evento. Devuelve un resumen."""
    repository.create_log(sensor_id, reading)

    if reading < DAMAGE_THRESHOLD:
        return {"anomalia": False}

    print(f"\nSENSOR {sensor_id} DAÑADO", flush=True)
    repository.mark_as_broken(sensor_id)
    alert_id = repository.create_alert(sensor_id, reading)
    published = publish_alert({
        "event": "sensor_damaged",
        "alert_id": alert_id,
        "sensor_id": sensor_id,
        "reading": reading,
        "timestamp": datetime.now().isoformat(),
    })
    return {"anomalia": True, "alert_id": alert_id, "publicada": published}
