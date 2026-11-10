"""
monitoring-service: Health Endpoint Monitoring agregado del sistema.

Consulta el /health de cada servicio (auth, sensor, statistics y alert) mediante un
ServiceClient con su propio Circuit Breaker y devuelve el estado general:

  status = "healthy"   -> todos los servicios sanos
  status = "degraded"  -> al menos uno no responde o está enfermo

Siempre responde HTTP 200 mientras el propio monitoring-service funcione: el estado agregado va
en el campo `status`. Así el Circuit Breaker del gateway no se abre justo cuando más se necesita
ver el detalle de qué servicio falla.
"""
from dotenv import load_dotenv

load_dotenv()

import os
from datetime import datetime, timezone
from time import perf_counter

from flask import Flask, jsonify

from common.resilience import ServiceClient, ServiceUnavailable

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


def _build_client(name, env_var, default_url):
    return ServiceClient(
        name,
        os.getenv(env_var, default_url),
        timeout=(float(os.getenv("MONITOR_CONNECT_TIMEOUT", "1")),
                 float(os.getenv("MONITOR_READ_TIMEOUT", "2"))),
        retries=0,
        failure_threshold=int(os.getenv("CB_FAILURE_THRESHOLD", "3")),
        recovery_timeout=float(os.getenv("CB_RECOVERY_TIMEOUT", "15")),
    )


clients = {
    "auth": _build_client("auth-service", "AUTH_SERVICE_URL", "http://auth-service:5001"),
    "sensor": _build_client("sensor-service", "SENSOR_SERVICE_URL", "http://sensor-service:5002"),
    "statistics": _build_client("statistics-service", "STATISTICS_SERVICE_URL",
                                "http://statistics-service:5003"),
    "alert": _build_client("alert-service", "ALERT_SERVICE_URL", "http://alert-service:5005"),
}


@app.route("/monitoring")
def monitoring():
    start_time = perf_counter()
    services = {}
    sensores = None

    for key, client in clients.items():
        try:
            resp = client.request("GET", "/health")
            data = resp.json() if resp.content else {}
            if resp.status_code == 200:
                services[client.name] = {"status": "healthy", "checks": data.get("checks", {})}
                if key == "sensor":
                    sensores = data.get("checks", {}).get("sensores")
            else:
                services[client.name] = {"status": "unhealthy", "http_status": resp.status_code,
                                         "checks": data.get("checks", {})}
        except ServiceUnavailable as exc:
            services[client.name] = {"status": "unreachable", "reason": exc.reason}
        except ValueError:
            services[client.name] = {"status": "unhealthy", "reason": "respuesta inválida"}

    all_healthy = all(s["status"] == "healthy" for s in services.values())

    return jsonify({
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "response_time_ms": round((perf_counter() - start_time) * 1000, 2),
        "checks": {"services": services, "sensores": sensores},
        "circuit_breakers": {c.name: c.breaker.snapshot() for c in clients.values()},
    }), 200


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "monitoring-service", "checks": {}}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=False)
