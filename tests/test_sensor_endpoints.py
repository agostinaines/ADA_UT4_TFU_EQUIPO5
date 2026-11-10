"""Endpoints REST del sensor-service (con repository y readings simulados)."""
import unittest
from unittest import mock

from flask import Flask

from _loader import load


class SensorEndpointsTests(unittest.TestCase):
    def setUp(self):
        self.repo = mock.Mock()
        self.repo.REPAIR_SECONDS = 30
        self.readings = mock.Mock()
        module = load("sensor_service", "sensors.py", "sensor_endpoints",
                      {"repository": self.repo, "readings": self.readings})
        app = Flask(__name__)
        app.register_blueprint(module.sensors)
        self.c = app.test_client()

    # ---- Asynchronous Request-Reply ----
    def test_repair_returns_202_with_ticket_location(self):
        self.repo.get_sensor.return_value = {"id": 4}
        with mock.patch("threading.Thread.start"):
            r = self.c.patch("/repairSensor/4")
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.headers["Location"], "/ticket/4")
        self.assertEqual(r.headers["Retry-After"], "30")
        self.assertEqual(r.get_json()["ticket_url"], "/ticket/4")

    def test_repair_unknown_sensor_is_404(self):
        self.repo.get_sensor.return_value = None
        self.assertEqual(self.c.patch("/repairSensor/99").status_code, 404)

    def test_ticket_reports_pending_then_done(self):
        self.repo.get_fixed.return_value = ("pending", "Su solicitud se sigue procesando")
        self.assertEqual(self.c.get("/ticket/4").get_json()["estado"], "pending")
        self.repo.get_fixed.return_value = ("done", "El sensor 4 fue reparado con éxito")
        self.assertEqual(self.c.get("/ticket/4").get_json()["estado"], "done")
        self.repo.get_fixed.return_value = None
        self.assertEqual(self.c.get("/ticket/4").status_code, 404)

    # ---- POST /readings (paso 1) ----
    def test_reading_is_processed(self):
        self.repo.get_sensor.return_value = {"id": 1, "activo": True, "roto": False}
        self.readings.process_reading.return_value = {"anomalia": False}
        r = self.c.post("/readings", json={"sensor_id": 1, "lectura": 0.42})
        self.assertEqual(r.status_code, 201)
        self.readings.process_reading.assert_called_once_with(1, 0.42)

    def test_reading_validation(self):
        for body in ({}, {"sensor_id": 1}, {"sensor_id": "1", "lectura": 0.5},
                     {"sensor_id": 1, "lectura": 1.5}, {"sensor_id": 1, "lectura": True}):
            self.assertEqual(self.c.post("/readings", json=body).status_code, 400, body)

    def test_reading_from_unknown_or_broken_sensor(self):
        self.repo.get_sensor.return_value = None
        self.assertEqual(self.c.post("/readings", json={"sensor_id": 9, "lectura": 0.1}).status_code, 404)
        self.repo.get_sensor.return_value = {"id": 9, "activo": True, "roto": True}
        self.assertEqual(self.c.post("/readings", json={"sensor_id": 9, "lectura": 0.1}).status_code, 409)

    # ---- uso interno ----
    def test_aggregate_endpoint(self):
        self.repo.aggregate_logs.return_value = [{"region": "Norte", "promedio": 0.5}]
        r = self.c.get("/internal/logs/aggregate?days=7")
        self.assertEqual(r.status_code, 200)
        self.repo.aggregate_logs.assert_called_once_with(7)
        self.assertEqual(self.c.get("/internal/logs/aggregate?days=abc").status_code, 400)

    def test_alert_ack(self):
        self.repo.confirm_alert.return_value = True
        self.assertEqual(self.c.post("/internal/alerts/abc/ack").status_code, 200)
        self.repo.confirm_alert.return_value = None
        self.assertEqual(self.c.post("/internal/alerts/zzz/ack").status_code, 404)


if __name__ == "__main__":
    unittest.main()
