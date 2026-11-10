"""Pasos 1 a 3 de la secuencia: llega una lectura, se detecta la anomalía y se publica el evento."""
import unittest
from unittest import mock

from _loader import fake_module, load


class ReadingsTests(unittest.TestCase):
    def setUp(self):
        self.repo = mock.Mock()
        self.repo.create_alert.return_value = "alert-123"
        self.pika = mock.MagicMock()
        self.readings = load("sensor_service", "readings.py", "sensor_readings",
                             {"repository": self.repo, "pika": self.pika})

    def test_normal_reading_is_only_stored(self):
        with mock.patch.object(self.readings, "publish_alert") as publish:
            result = self.readings.process_reading(1, 0.5)
        self.assertEqual(result, {"anomalia": False})
        self.repo.create_log.assert_called_once_with(1, 0.5)
        self.repo.mark_as_broken.assert_not_called()
        publish.assert_not_called()

    def test_anomaly_marks_sensor_creates_alert_and_publishes(self):
        with mock.patch.object(self.readings, "publish_alert", return_value=True) as publish:
            result = self.readings.process_reading(7, 0.995)
        self.assertTrue(result["anomalia"])
        self.assertEqual(result["alert_id"], "alert-123")
        self.assertTrue(result["publicada"])
        self.repo.mark_as_broken.assert_called_once_with(7)
        self.repo.create_alert.assert_called_once_with(7, 0.995)
        event = publish.call_args[0][0]
        self.assertEqual(event["event"], "sensor_damaged")
        self.assertEqual(event["alert_id"], "alert-123")
        self.assertEqual(event["sensor_id"], 7)

    def test_threshold_is_inclusive(self):
        with mock.patch.object(self.readings, "publish_alert", return_value=True):
            self.assertTrue(self.readings.process_reading(1, self.readings.DAMAGE_THRESHOLD)["anomalia"])

    def test_publish_is_retried_then_reports_failure(self):
        self.readings.PUBLISH_BACKOFF = 0
        with mock.patch.object(self.readings, "_publish_once", side_effect=OSError("rabbit down")) as once:
            self.assertFalse(self.readings.publish_alert({"event": "sensor_damaged"}))
        self.assertEqual(once.call_count, self.readings.PUBLISH_ATTEMPTS)

    def test_publish_succeeds_after_a_transient_failure(self):
        self.readings.PUBLISH_BACKOFF = 0
        with mock.patch.object(self.readings, "_publish_once", side_effect=[OSError("x"), None]) as once:
            self.assertTrue(self.readings.publish_alert({"event": "sensor_damaged"}))
        self.assertEqual(once.call_count, 2)

    def test_anomaly_is_not_lost_if_rabbitmq_is_down(self):
        """El sensor queda roto y la alerta registrada como pendiente aunque no se pueda publicar."""
        with mock.patch.object(self.readings, "publish_alert", return_value=False):
            result = self.readings.process_reading(3, 0.999)
        self.assertFalse(result["publicada"])
        self.repo.mark_as_broken.assert_called_once_with(3)
        self.repo.create_alert.assert_called_once()


if __name__ == "__main__":
    unittest.main()
