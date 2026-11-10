"""
sensor-service: dueño de los sensores, las lecturas y la detección de anomalías (base sensor_db).

Responsabilidades:
  - REST:  /allSensors, /newSensor, /repairSensor/<id>, /ticket/<id>, /toggleSensor/<id>
  - REST:  POST /readings (un sensor envía una lectura), /getAllLogs, /getAll/<id>/logs, /allAlerts
  - SOAP:  /soap/sensors  (operación GetSensorStatus, ex GET /sensorStatus)
  - Eventos: detecta anomalías y publica 'sensor_damaged' en RabbitMQ (AMQP)
  - Interno: /internal/logs/aggregate (para Statistics), /internal/alerts/<id>/ack (confirma el Alert Service)
  - Simulación de sensores que generan lecturas periódicas
  - GET /health : Health Endpoint Monitoring de este servicio
"""
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify

import repository
import simulation
from sensors import sensors
from soap_service import soap

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.register_blueprint(sensors)
app.register_blueprint(soap)


@app.route("/health")
def health():
    try:
        summary = repository.get_summary()
        return jsonify({
            "status": "healthy",
            "service": "sensor-service",
            "checks": {
                "database": "conectado a la base de datos",
                "sensores": summary,
                "simulacion": simulation.status(),
            },
        }), 200
    except Exception:
        return jsonify({
            "status": "unhealthy",
            "service": "sensor-service",
            "checks": {"database": "unhealthy"},
        }), 503


if __name__ == "__main__":
    simulation.start_background_tasks()
    app.run(host="0.0.0.0", port=5002, debug=False)
