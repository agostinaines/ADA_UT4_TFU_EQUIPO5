"""
Cliente SOAP del gateway: consume la operación GetSensorStatus del sensor-service
(contrato: sensor_status.wsdl, namespace y soapAction idénticos a los del WSDL).
"""
import xml.etree.ElementTree as ET

import requests

SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
NS = "http://tfu.ucu.edu.uy/sensors"
SOAP_ACTION = "http://tfu.ucu.edu.uy/sensors/GetSensorStatus"

REQUEST_ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    f'<soap:Envelope xmlns:soap="{SOAP_ENV}" xmlns:tns="{NS}">'
    "<soap:Body><tns:GetSensorStatusRequest/></soap:Body></soap:Envelope>"
)


class SoapFault(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.ignore_for_breaker = "Client" in (code or "")


def get_sensor_status(url, timeout=(1.0, 5.0)):
    """Invoca GetSensorStatus y devuelve [{'id': int, 'estado': str}, ...]."""
    resp = requests.post(
        url,
        data=REQUEST_ENVELOPE.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{SOAP_ACTION}"',
        },
        timeout=timeout,
    )

    try:
        root = ET.fromstring(resp.content)
        body = root.find(f"{{{SOAP_ENV}}}Body")
    except ET.ParseError:
        body = None

    if body is None:
        raise SoapFault("soap:Server", f"Respuesta SOAP inválida (HTTP {resp.status_code})")

    fault = body.find(f"{{{SOAP_ENV}}}Fault")
    if fault is not None:
        raise SoapFault(fault.findtext("faultcode"), fault.findtext("faultstring"))

    response = body.find(f"{{{NS}}}GetSensorStatusResponse")
    if response is None:
        raise SoapFault("soap:Server", "Falta GetSensorStatusResponse en la respuesta")

    return [
        {"id": int(s.findtext(f"{{{NS}}}id")), "estado": s.findtext(f"{{{NS}}}estado")}
        for s in response.findall(f"{{{NS}}}sensor")
    ]
