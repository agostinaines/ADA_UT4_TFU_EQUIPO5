"""Monitoring Service: estado agregado de los demás servicios."""
import unittest
from unittest import mock

from common.resilience import ServiceUnavailable

from _loader import load


def fake_resp(status=200, body=b'{"status":"healthy","checks":{}}'):
    r = mock.Mock()
    r.status_code = status
    r.content = body
    r.json = lambda: __import__("json").loads(body)
    return r


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.mod = load("monitoring_service", "main.py", "monitoring_main", {})
        self.c = self.mod.app.test_client()
        for client in self.mod.clients.values():
            client.breaker._on_success()

    def _patch_all(self, overrides=None):
        overrides = overrides or {}
        patches = []
        for key, client in self.mod.clients.items():
            effect = overrides.get(key)
            if isinstance(effect, Exception):
                p = mock.patch.object(client, "request", side_effect=effect)
            else:
                p = mock.patch.object(client, "request", return_value=effect or fake_resp())
            patches.append(p)
        return patches

    def test_all_healthy(self):
        sensor_ok = fake_resp(body=b'{"status":"healthy","checks":{"sensores":{"total":6,"activos":6,"rotos":0}}}')
        ps = self._patch_all({"sensor": sensor_ok})
        for p in ps:
            p.start()
        try:
            body = self.c.get("/monitoring").get_json()
        finally:
            for p in ps:
                p.stop()
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(set(body["checks"]["services"]),
                         {"auth-service", "sensor-service", "statistics-service", "alert-service"})
        self.assertEqual(body["checks"]["sensores"]["total"], 6)
        self.assertIn("circuit_breakers", body)

    def test_degraded_when_a_service_is_down_but_http_is_200(self):
        down = ServiceUnavailable("alert-service", "unreachable")
        ps = self._patch_all({"alert": down, "statistics": fake_resp(503, b'{"checks":{"database":"unhealthy"}}')})
        for p in ps:
            p.start()
        try:
            r = self.c.get("/monitoring")
        finally:
            for p in ps:
                p.stop()
        body = r.get_json()
        self.assertEqual(r.status_code, 200)  # no dispara el breaker del gateway
        self.assertEqual(body["status"], "degraded")
        self.assertEqual(body["checks"]["services"]["alert-service"]["status"], "unreachable")
        self.assertEqual(body["checks"]["services"]["statistics-service"]["status"], "unhealthy")
        self.assertEqual(body["checks"]["services"]["auth-service"]["status"], "healthy")

    def test_health(self):
        self.assertEqual(self.c.get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
