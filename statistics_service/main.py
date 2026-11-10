"""
statistics-service: estadísticas mensuales por región (base statistics_db).

  - GET /getMonthlyStats    : lee la vista materializada local (sigue funcionando aunque el
                              sensor-service esté caído).
  - GET /insertMonthlyStats : pide el agregado de lecturas al sensor-service (REST) y recalcula
                              la vista materializada. Esa llamada está protegida por Timeout +
                              Retry + Circuit Breaker (common.resilience): si el sensor-service
                              no responde, se devuelve 503 rápido en vez de seguir insistiendo.
  - GET /health             : Health Endpoint Monitoring de este servicio.
"""
from dotenv import load_dotenv

load_dotenv()

import os

from flask import Flask, jsonify

import repository
from common.resilience import ServiceClient, ServiceUnavailable

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

STATS_WINDOW_DAYS = int(os.getenv("STATS_WINDOW_DAYS", "30"))

sensor_client = ServiceClient(
    "sensor-service",
    os.getenv("SENSOR_SERVICE_URL", "http://sensor-service:5002"),
    timeout=(float(os.getenv("UPSTREAM_CONNECT_TIMEOUT", "1")),
             float(os.getenv("UPSTREAM_READ_TIMEOUT", "5"))),
    retries=int(os.getenv("UPSTREAM_RETRIES", "2")),
    failure_threshold=int(os.getenv("CB_FAILURE_THRESHOLD", "3")),
    recovery_timeout=float(os.getenv("CB_RECOVERY_TIMEOUT", "15")),
)


def _error():
    return jsonify({"success": False, "description": "Internal server error"}), 500


@app.route("/getMonthlyStats")
def get_monthly_stats():
    try:
        return jsonify({"success": True, "logs": repository.get_monthly_stats()}), 200
    except Exception:
        return _error()


@app.route("/insertMonthlyStats")
def insert_monthly_stats():
    try:
        resp = sensor_client.request("GET", "/internal/logs/aggregate",
                                     params={"days": STATS_WINDOW_DAYS})
    except ServiceUnavailable as exc:
        response = jsonify({
            "success": False,
            "description": f"Servicio '{exc.service}' no disponible",
            "reason": exc.reason,
        })
        response.status_code = 503
        if exc.retry_after:
            response.headers["Retry-After"] = str(exc.retry_after)
        return response

    if resp.status_code != 200:
        return jsonify({"success": False,
                        "description": f"sensor-service respondió {resp.status_code}"}), 502

    try:
        repository.save_monthly_stats(resp.json()["stats"])
        return jsonify({"success": True}), 200
    except Exception:
        return _error()


@app.route("/health")
def health():
    try:
        repository.ping()
    except Exception:
        return jsonify({
            "status": "unhealthy",
            "service": "statistics-service",
            "checks": {"database": "unhealthy"},
        }), 503

    return jsonify({
        "status": "healthy",
        "service": "statistics-service",
        "checks": {
            "database": "conectado a la base de datos",
            "circuit_breaker_sensor_service": sensor_client.breaker.snapshot(),
        },
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=False)
