"""
API Gateway: único punto de entrada público del sistema (puerto 5000).

Responsabilidades:
  - Gateway Routing: enruta cada endpoint público al microservicio dueño.
  - Gateway Offloading: valida el JWT y el rol una sola vez (los servicios internos
    no se publican y reciben la identidad en X-User-Mail / X-User-Role).
  - Resiliencia: timeouts + retry + Circuit Breaker por cada servicio (common.resilience).
    Si un servicio cae, el gateway responde 503 rápido y el resto del sistema sigue.
  - /monitoring se enruta al monitoring-service (Health Endpoint Monitoring agregado).
  - Consumidor SOAP: /sensorStatus (REST hacia el cliente) invoca por SOAP al sensor-service.
"""
from dotenv import load_dotenv

load_dotenv()

import os
import re

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt

import soap_client
from common.resilience import ServiceClient, ServiceUnavailable
from decorators import roles_required

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})
app.config["JWT_SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JSON_AS_ASCII"] = False
JWTManager(app)


def _build_client(name, env_var, default_url):
    return ServiceClient(
        name,
        os.getenv(env_var, default_url),
        timeout=(float(os.getenv("UPSTREAM_CONNECT_TIMEOUT", "1")),
                 float(os.getenv("UPSTREAM_READ_TIMEOUT", "5"))),
        retries=int(os.getenv("UPSTREAM_RETRIES", "2")),
        failure_threshold=int(os.getenv("CB_FAILURE_THRESHOLD", "3")),
        recovery_timeout=float(os.getenv("CB_RECOVERY_TIMEOUT", "15")),
    )


clients = {
    "auth": _build_client("auth-service", "AUTH_SERVICE_URL", "http://auth-service:5001"),
    "sensor": _build_client("sensor-service", "SENSOR_SERVICE_URL", "http://sensor-service:5002"),
    "statistics": _build_client("statistics-service", "STATISTICS_SERVICE_URL",
                                "http://statistics-service:5003"),
    "monitoring": _build_client("monitoring-service", "MONITORING_SERVICE_URL",
                                "http://monitoring-service:5004"),
    "alert": _build_client("alert-service", "ALERT_SERVICE_URL", "http://alert-service:5005"),
}
SENSOR_SOAP_URL = os.getenv("SENSOR_SOAP_URL", clients["sensor"].base_url + "/soap/sensors")

ROUTES = [
    ("/register", ["POST"], None, "auth", None),
    ("/login", ["POST"], None, "auth", None),
    ("/valetKey", ["POST"], "operador", "auth", None),

    ("/allSensors", ["GET"], "operador", "sensor", None),
    ("/newSensor", ["POST"], "operador", "sensor", None),
    ("/repairSensor/<id>", ["PATCH"], "operador", "sensor", None),
    ("/ticket/<id>", ["GET"], "operador", "sensor", None),
    ("/toggleSensor/<id>", ["PATCH"], "operador", "sensor", None),
    ("/readings", ["POST"], "valet", "sensor", None),
    ("/getAllLogs", ["GET"], "operador", "sensor", None),
    ("/getAll/<id>/logs", ["GET"], "operador", "sensor", None),
    ("/allAlerts", ["GET"], "operador", "sensor", None),
    ("/soap/sensors", ["POST"], "valet", "sensor", None),
    ("/soap/sensors.wsdl", ["GET"], None, "sensor", "/soap/sensors?wsdl"),

    ("/getMonthlyStats", ["GET"], "operador", "statistics", None),
    ("/insertMonthlyStats", ["GET"], "operador", "statistics", None),

    ("/monitoring", ["GET"], "operador", "monitoring", None),
    ("/alerts", ["GET"], "operador", "alert", None),
]


def unavailable(exc):
    response = jsonify({
        "success": False,
        "description": f"Servicio '{exc.service}' no disponible",
        "reason": exc.reason,
    })
    response.status_code = 503
    if exc.retry_after:
        response.headers["Retry-After"] = str(exc.retry_after)
    return response


def forward(service, upstream, authenticated):
    headers = {h: request.headers[h] for h in ("Content-Type", "Accept", "SOAPAction")
               if request.headers.get(h)}
    if authenticated:
        claims = get_jwt()
        headers["X-User-Mail"] = claims.get("sub", "")
        headers["X-User-Role"] = claims.get("rol", "")

    try:
        resp = clients[service].request(
            request.method,
            upstream or request.path,
            data=request.get_data(),
            headers=headers,
            params=None if upstream else request.args.to_dict(flat=False),
        )
    except ServiceUnavailable as exc:
        return unavailable(exc)

    return Response(resp.content, status=resp.status_code,
                    content_type=resp.headers.get("Content-Type"))


def _make_view(service, role, upstream):
    def view(**kwargs):
        return forward(service, upstream, authenticated=role is not None)

    return roles_required(role)(view) if role else view


for rule, methods, role, service, upstream in ROUTES:
    endpoint = re.sub(r"\W", "_", f"proxy_{service}_{rule}_{'_'.join(methods)}")
    app.add_url_rule(rule, endpoint=endpoint, view_func=_make_view(service, role, upstream),
                     methods=methods)


@app.route("/")
def welcome():
    return "¡Bienvenido!"


@app.route("/sensorStatus")
@roles_required("valet")
def sensor_status_endpoint():
    """Fachada REST -> SOAP: el cliente sigue usando REST, el gateway consume el SOAP del sensor-service."""
    sensor_client = clients["sensor"]
    try:
        sensors = sensor_client.guard(
            lambda: soap_client.get_sensor_status(SENSOR_SOAP_URL, timeout=sensor_client.timeout)
        )
    except ServiceUnavailable as exc:
        return unavailable(exc)
    except soap_client.SoapFault as exc:
        return jsonify({"success": False, "description": f"Error SOAP: {exc.message}"}), 502

    return jsonify({"success": True, "sensors": sensors}), 200


@app.route("/health")
def health():
    """Healthcheck del propio gateway (lo usa Docker Compose)."""
    return jsonify({"status": "healthy", "service": "gateway"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
