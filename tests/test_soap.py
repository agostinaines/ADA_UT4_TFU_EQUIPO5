"""Ida y vuelta SOAP: el cliente del gateway contra el servidor SOAP del sensor-service (sin red)."""
import os
import sys
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "sensor_service"))
sys.path.insert(0, os.path.join(ROOT, "gateway"))

from flask import Flask

import soap_client
import soap_service

FAKE_SENSORS = [{"id": 1, "activo": True, "roto": False},
                {"id": 2, "activo": False, "roto": True}]


def make_app():
    app = Flask(__name__)
    app.register_blueprint(soap_service.soap)
    return app


class SoapTests(unittest.TestCase):
    def setUp(self):
        self.client = make_app().test_client()

    def _post_via_test_client(self, url, data=None, headers=None, timeout=None):
        r = self.client.post("/soap/sensors", data=data, headers=headers)
        fake = mock.Mock()
        fake.content = r.data
        fake.status_code = r.status_code
        return fake

    @mock.patch("soap_service.repository.get_all", return_value=FAKE_SENSORS)
    def test_client_consumes_service(self, _):
        with mock.patch("soap_client.requests.post", side_effect=self._post_via_test_client):
            result = soap_client.get_sensor_status("http://ignored/soap/sensors")
        self.assertEqual(result, [{"id": 1, "estado": "saludable"}, {"id": 2, "estado": "roto"}])

    def test_wsdl_is_served_and_well_formed(self):
        r = self.client.get("/soap/sensors?wsdl")
        self.assertEqual(r.status_code, 200)
        root = ET.fromstring(r.data)
        self.assertTrue(root.tag.endswith("definitions"))
        self.assertIn(b"http://localhost:5000/soap/sensors", r.data)
        self.assertIn(b"GetSensorStatus", r.data)

    def test_invalid_xml_returns_client_fault(self):
        r = self.client.post("/soap/sensors", data="no es xml")
        self.assertEqual(r.status_code, 500)
        self.assertIn(b"soap:Client", r.data)

    def test_unknown_operation_returns_client_fault(self):
        env = ('<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
               '<soap:Body><x:Otra xmlns:x="urn:x"/></soap:Body></soap:Envelope>')
        r = self.client.post("/soap/sensors", data=env)
        self.assertEqual(r.status_code, 500)
        self.assertIn(b"Operaci", r.data)

    @mock.patch("soap_service.repository.get_all", side_effect=RuntimeError("db"))
    def test_server_fault_is_raised_by_client(self, _):
        with mock.patch("soap_client.requests.post", side_effect=self._post_via_test_client):
            with self.assertRaises(soap_client.SoapFault) as ctx:
                soap_client.get_sensor_status("http://ignored")
        self.assertFalse(ctx.exception.ignore_for_breaker)

    def test_client_fault_does_not_trip_breaker(self):
        self.assertTrue(soap_client.SoapFault("soap:Client", "x").ignore_for_breaker)


if __name__ == "__main__":
    unittest.main()
