"""
Tests del gateway sin Docker. Si flask_jwt_extended no está instalado se usa un stub mínimo
(token de prueba: "Bearer <rol>:<mail>") para poder verificar enrutamiento, roles y 503.
"""
import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "gateway"))

try:
    import flask_jwt_extended  # noqa: F401
    REAL_JWT = True
except ImportError:
    REAL_JWT = False
    from functools import wraps
    from flask import g, jsonify, request

    stub = types.ModuleType("flask_jwt_extended")

    class JWTManager:
        def __init__(self, app=None):
            pass

    def jwt_required():
        def deco(fn):
            @wraps(fn)
            def wrapper(*a, **k):
                auth = request.headers.get("Authorization", "")
                if not auth.startswith("Bearer "):
                    return jsonify({"msg": "Missing Authorization Header"}), 401
                rol, mail = auth[7:].split(":")
                g.claims = {"rol": rol, "sub": mail}
                return fn(*a, **k)
            return wrapper
        return deco

    stub.JWTManager = JWTManager
    stub.jwt_required = jwt_required
    stub.get_jwt = lambda: g.claims
    sys.modules["flask_jwt_extended"] = stub

if "flask_cors" not in sys.modules:
    try:
        import flask_cors  # noqa: F401
    except ImportError:
        s = types.ModuleType("flask_cors")
        s.CORS = lambda *a, **k: None
        sys.modules["flask_cors"] = s

import main as gw  # noqa: E402
from common.resilience import ServiceUnavailable  # noqa: E402


def fake_resp(status=200, json_body=b'{"success": true}', ctype="application/json"):
    r = mock.Mock()
    r.status_code = status
    r.content = json_body
    r.headers = {"Content-Type": ctype}
    r.json = lambda: __import__("json").loads(json_body)
    return r


@unittest.skipIf(REAL_JWT, "tokens de prueba solo válidos con el stub")
class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.c = gw.app.test_client()
        for client in gw.clients.values():
            client.breaker._on_success()

    def hdr(self, role):
        return {"Authorization": f"Bearer {role}:user@x.com"}

    def test_all_declared_routes_are_registered(self):
        rules = {r.rule for r in gw.app.url_map.iter_rules()}
        for rule, *_ in gw.ROUTES:
            self.assertIn(rule, rules)
        self.assertIn("/sensorStatus", rules)
        self.assertIn("/health", rules)

    def test_routes_go_to_the_service_that_owns_them(self):
        owners = {rule: service for rule, _, _, service, _ in gw.ROUTES}
        self.assertEqual(owners["/getAllLogs"], "sensor")
        self.assertEqual(owners["/readings"], "sensor")
        self.assertEqual(owners["/getMonthlyStats"], "statistics")
        self.assertEqual(owners["/insertMonthlyStats"], "statistics")
        self.assertEqual(owners["/monitoring"], "monitoring")
        self.assertEqual(owners["/alerts"], "alert")
        self.assertEqual(set(gw.clients), {"auth", "sensor", "statistics", "monitoring", "alert"})

    def test_public_route_forwards_without_token(self):
        with mock.patch.object(gw.clients["auth"], "request", return_value=fake_resp()) as m:
            r = self.c.post("/login", json={"mail": "a", "contrasenia": "b"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(m.call_args[0][:2], ("POST", "/login"))

    def test_protected_route_requires_token(self):
        self.assertEqual(self.c.get("/allSensors").status_code, 401)

    def test_wrong_role_is_403(self):
        self.assertEqual(self.c.get("/allSensors", headers=self.hdr("valet")).status_code, 403)
        self.assertEqual(self.c.get("/sensorStatus", headers=self.hdr("operador")).status_code, 403)

    def test_identity_headers_are_propagated(self):
        with mock.patch.object(gw.clients["sensor"], "request", return_value=fake_resp()) as m:
            r = self.c.get("/allSensors", headers=self.hdr("operador"))
        self.assertEqual(r.status_code, 200)
        sent = m.call_args.kwargs["headers"]
        self.assertEqual(sent["X-User-Role"], "operador")
        self.assertEqual(sent["X-User-Mail"], "user@x.com")

    def test_service_down_gives_503_with_retry_after(self):
        exc = ServiceUnavailable("sensor-service", "circuit_open", retry_after=9)
        with mock.patch.object(gw.clients["sensor"], "request", side_effect=exc):
            r = self.c.get("/allSensors", headers=self.hdr("operador"))
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.headers["Retry-After"], "9")
        self.assertEqual(r.get_json()["reason"], "circuit_open")

    def test_one_service_down_does_not_affect_others(self):
        exc = ServiceUnavailable("sensor-service", "unreachable")
        with mock.patch.object(gw.clients["sensor"], "request", side_effect=exc), \
             mock.patch.object(gw.clients["statistics"], "request", return_value=fake_resp()):
            self.assertEqual(self.c.get("/allSensors", headers=self.hdr("operador")).status_code, 503)
            self.assertEqual(self.c.get("/getMonthlyStats", headers=self.hdr("operador")).status_code, 200)

    def test_sensor_status_facade_uses_soap(self):
        with mock.patch("main.soap_client.get_sensor_status",
                        return_value=[{"id": 1, "estado": "roto"}]) as m:
            r = self.c.get("/sensorStatus", headers=self.hdr("valet"))
        self.assertEqual(r.get_json(), {"success": True, "sensors": [{"id": 1, "estado": "roto"}]})
        m.assert_called_once()

    def test_monitoring_is_forwarded_to_monitoring_service(self):
        with mock.patch.object(gw.clients["monitoring"], "request", return_value=fake_resp()) as m:
            r = self.c.get("/monitoring", headers=self.hdr("operador"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(m.call_args[0][:2], ("GET", "/monitoring"))
        self.assertEqual(self.c.get("/monitoring", headers=self.hdr("valet")).status_code, 403)

    def test_alerts_are_forwarded_to_alert_service(self):
        with mock.patch.object(gw.clients["alert"], "request", return_value=fake_resp()) as m:
            r = self.c.get("/alerts", headers=self.hdr("operador"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(m.call_args[0][:2], ("GET", "/alerts"))

    def test_readings_require_valet_key(self):
        self.assertEqual(self.c.post("/readings", json={}).status_code, 401)
        self.assertEqual(self.c.post("/readings", json={}, headers=self.hdr("operador")).status_code, 403)
        with mock.patch.object(gw.clients["sensor"], "request", return_value=fake_resp(201)) as m:
            r = self.c.post("/readings", json={"sensor_id": 1, "lectura": 0.5}, headers=self.hdr("valet"))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(m.call_args[0][:2], ("POST", "/readings"))

    def test_gateway_health_is_public(self):
        self.assertEqual(self.c.get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
