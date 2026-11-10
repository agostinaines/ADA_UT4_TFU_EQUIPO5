"""
Servicio SOAP del sensor-service (migración de REST/JSON -> SOAP/XML).

Operación migrada: GET /sensorStatus (REST)  ->  GetSensorStatus (SOAP).
  - Contrato:  GET /soap/sensors?wsdl   (archivo sensor_status.wsdl)
  - Endpoint:  POST /soap/sensors       (SOAP 1.1, document/literal)

Se implementa con la librería estándar (xml.etree) para no sumar dependencias.
"""
import os
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from flask import Blueprint, Response, request

import repository

soap = Blueprint("soap", __name__)

SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
NS = "http://tfu.ucu.edu.uy/sensors"
WSDL_PATH = os.path.join(os.path.dirname(__file__), "sensor_status.wsdl")


def _envelope(body_xml):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<soap:Envelope xmlns:soap="{SOAP_ENV}" xmlns:tns="{NS}">'
        f"<soap:Body>{body_xml}</soap:Body></soap:Envelope>"
    )


def _fault(code, message):
    xml = _envelope(
        f"<soap:Fault><faultcode>soap:{code}</faultcode>"
        f"<faultstring>{escape(message)}</faultstring></soap:Fault>"
    )
    return Response(xml, status=500, content_type="text/xml; charset=utf-8")


def _get_sensor_status():
    sensors = repository.get_all()
    items = "".join(
        "<tns:sensor>"
        f"<tns:id>{int(s['id'])}</tns:id>"
        f"<tns:estado>{'roto' if s['roto'] else 'saludable'}</tns:estado>"
        "</tns:sensor>"
        for s in sensors
    )
    return f"<tns:GetSensorStatusResponse>{items}</tns:GetSensorStatusResponse>"


OPERATIONS = {"GetSensorStatusRequest": _get_sensor_status}


@soap.route("/soap/sensors", methods=["GET", "POST"])
def soap_endpoint():
    if request.method == "GET":
        if "wsdl" not in request.args:
            return Response("Use ?wsdl para obtener el contrato", status=400, mimetype="text/plain")
        location = os.getenv("SOAP_PUBLIC_URL", "http://localhost:5000/soap/sensors")
        with open(WSDL_PATH, encoding="utf-8") as f:
            wsdl = f.read().replace("{{SOAP_LOCATION}}", location)
        return Response(wsdl, content_type="text/xml; charset=utf-8")

    try:
        root = ET.fromstring(request.get_data())
    except ET.ParseError:
        return _fault("Client", "El mensaje no es XML válido")

    body = root.find(f"{{{SOAP_ENV}}}Body")
    if body is None or len(body) == 0:
        return _fault("Client", "Falta el elemento Body o está vacío")

    operation_name = body[0].tag.rsplit("}", 1)[-1]
    operation = OPERATIONS.get(operation_name)
    if operation is None:
        return _fault("Client", f"Operación desconocida: {operation_name}")

    try:
        return Response(_envelope(operation()), content_type="text/xml; charset=utf-8")
    except Exception:
        return _fault("Server", "Error interno al consultar los sensores")
