"""
Endpoints REST del sensor-service.

Los que empiezan con /internal/ los consumen otros servicios (no se exponen en el gateway).
"""
from threading import Thread

from flask import Blueprint, jsonify, request

import readings
import repository

sensors = Blueprint("sensors", __name__)

REGIONES = ["Norte", "Sur", "Este", "Oeste"]


@sensors.route("/allSensors")
def get_all_sensors_endpoint():
    try:
        return jsonify({"success": True, "sensors": repository.get_all()}), 200
    except Exception:
        return jsonify({"success": False, "description": "Internal server error"}), 500


@sensors.route("/newSensor", methods=["POST"])
def new_sensor_endpoint():
    try:
        body = request.get_json()
        version = body.get("version")
        region = body.get("region")

        if not version or not region:
            return jsonify({"success": False, "description": "Faltan datos obligatorios"}), 400

        if region not in REGIONES:
            return jsonify({"success": False, "description": "Región inválida"}), 400

        repository.create(version, region)
        return jsonify({"success": True, "description": "Nuevo sensor registrado"}), 201
    except Exception:
        return jsonify({"success": False, "description": "Error"}), 500

@sensors.route("/readings", methods=["POST"])
def new_reading_endpoint():
    """Paso 1 de la secuencia: un sensor envía una lectura (0.0 a 1.0)."""
    body = request.get_json(silent=True) or {}
    sensor_id = body.get("sensor_id")
    lectura = body.get("lectura")

    valid_id = isinstance(sensor_id, int) and not isinstance(sensor_id, bool)
    valid_reading = (isinstance(lectura, (int, float)) and not isinstance(lectura, bool)
                     and 0 <= lectura <= 1)
    if not valid_id or not valid_reading:
        return jsonify({"success": False,
                        "description": "Se requiere sensor_id (entero) y lectura (número entre 0 y 1)"}), 400

    try:
        sensor = repository.get_sensor(sensor_id)
        if sensor is None:
            return jsonify({"success": False, "description": "Sensor no encontrado"}), 404
        if sensor["roto"] or not sensor["activo"]:
            return jsonify({"success": False, "description": "El sensor está apagado o roto"}), 409

        result = readings.process_reading(sensor_id, float(lectura))
        return jsonify({"success": True, **result}), 201
    except Exception:
        return jsonify({"success": False, "description": "Internal server error"}), 500


@sensors.route("/getAllLogs")
def get_all_logs_endpoint():
    try:
        return jsonify({"success": True, "logs": repository.get_all_logs()}), 200
    except Exception:
        return jsonify({"success": False, "description": "Internal server error"}), 500


@sensors.route("/getAll/<id>/logs")
def get_all_sensor_logs_endpoint(id):
    try:
        return jsonify({"success": True, "logs": repository.get_all_sensor_logs(id)}), 200
    except Exception:
        return jsonify({"success": False, "description": "Internal server error"}), 500

@sensors.route("/repairSensor/<id>", methods=["PATCH"])
def repair_sensor_endpoint(id):
    """
    Asynchronous Request-Reply: responde 202 de inmediato con el identificador del ticket
    (header Location + ticket_url) y repara en segundo plano. El cliente consulta el estado
    en GET /ticket/<id>.
    """
    try:
        if repository.get_sensor(id) is None:
            return jsonify({"success": False, "description": "Sensor no encontrado"}), 404

        Thread(target=repository.mark_as_fixed, args=(id,), daemon=True).start()

        response = jsonify({
            "success": True,
            "description": f"Ticket para reparar sensor {id} enviado con éxito",
            "ticket_url": f"/ticket/{id}",
        })
        response.status_code = 202
        response.headers["Location"] = f"/ticket/{id}"
        response.headers["Retry-After"] = str(repository.REPAIR_SECONDS)
        return response
    except Exception:
        return jsonify({"success": False, "description": "Error"}), 500


@sensors.route("/ticket/<id>")
def check_ticket_status(id):
    try:
        result = repository.get_fixed(id)
        if result is None:
            return jsonify({"success": False, "description": "Sensor no encontrado"}), 404
        estado, description = result
        return jsonify({"success": True, "estado": estado, "description": description}), 200
    except Exception:
        return jsonify({"success": False, "description": "Error"}), 500


@sensors.route("/toggleSensor/<id>", methods=["PATCH"])
def toggle_sensor_endpoint(id):
    try:
        description = repository.toggle_sensor(id)
        if description is None:
            return jsonify({"success": False, "description": "Sensor no encontrado"}), 404
        return jsonify({"success": True, "description": description}), 200
    except Exception:
        return jsonify({"success": False, "description": "Error"}), 500

@sensors.route("/allAlerts")
def get_all_alerts_endpoint():
    """Alertas generadas y si el Alert Service ya las confirmó (pendiente / confirmada)."""
    try:
        return jsonify({"success": True, "alerts": repository.get_all_alerts()}), 200
    except Exception:
        return jsonify({"success": False, "description": "Internal server error"}), 500

@sensors.route("/internal/logs/aggregate")
def internal_logs_aggregate():
    """Agregado por región de las lecturas recientes (lo consume el Statistics Service)."""
    try:
        days = int(request.args.get("days", 30))
        if days < 1 or days > 3650:
            raise ValueError
    except ValueError:
        return jsonify({"success": False, "description": "days debe ser un entero entre 1 y 3650"}), 400

    try:
        return jsonify({"success": True, "stats": repository.aggregate_logs(days)}), 200
    except Exception:
        return jsonify({"success": False, "description": "Internal server error"}), 500


@sensors.route("/internal/alerts/<alert_id>/ack", methods=["POST"])
def internal_alert_ack(alert_id):
    """Paso 8 de la secuencia: el Alert Service confirma que procesó la alerta."""
    try:
        if repository.confirm_alert(alert_id) is None:
            return jsonify({"success": False, "description": "Alerta no encontrada"}), 404
        return jsonify({"success": True}), 200
    except Exception:
        return jsonify({"success": False, "description": "Internal server error"}), 500
