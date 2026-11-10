"""Statistics Service: consulta al Sensor Service protegida por Circuit Breaker."""
import unittest
from unittest import mock

from common.resilience import ServiceUnavailable

from _loader import load


def fake_resp(status=200, body=None):
    r = mock.Mock()
    r.status_code = status
    r.json = lambda: body or {}
    return r


class StatisticsTests(unittest.TestCase):
    def setUp(self):
        self.repo = mock.Mock()
        self.mod = load("statistics_service", "main.py", "statistics_main", {"repository": self.repo})
        self.c = self.mod.app.test_client()
        self.mod.sensor_client.breaker._on_success()

    def test_insert_recomputes_from_sensor_service(self):
        stats = [{"region": "Norte", "promedio": 0.5, "minimo": 0.1, "maximo": 0.9, "cantidad_lecturas": 4}]
        with mock.patch.object(self.mod.sensor_client, "request",
                               return_value=fake_resp(200, {"stats": stats})) as m:
            r = self.c.get("/insertMonthlyStats")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(m.call_args[0][:2], ("GET", "/internal/logs/aggregate"))
        self.repo.save_monthly_stats.assert_called_once_with(stats)

    def test_sensor_service_down_gives_503_and_reads_keep_working(self):
        exc = ServiceUnavailable("sensor-service", "circuit_open", retry_after=9)
        self.repo.get_monthly_stats.return_value = []
        with mock.patch.object(self.mod.sensor_client, "request", side_effect=exc):
            r = self.c.get("/insertMonthlyStats")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.headers["Retry-After"], "9")
        self.assertEqual(r.get_json()["reason"], "circuit_open")
        self.repo.save_monthly_stats.assert_not_called()
        # la vista materializada ya calculada sigue disponible
        self.assertEqual(self.c.get("/getMonthlyStats").status_code, 200)

    def test_upstream_error_is_502(self):
        with mock.patch.object(self.mod.sensor_client, "request", return_value=fake_resp(404)):
            self.assertEqual(self.c.get("/insertMonthlyStats").status_code, 502)

    def test_health_reports_breaker(self):
        r = self.c.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertIn("circuit_breaker_sensor_service", r.get_json()["checks"])


if __name__ == "__main__":
    unittest.main()
