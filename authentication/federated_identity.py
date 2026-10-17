import json
import os
from urllib import error, request


FIREBASE_AUTH_BASE_URL = "https://identitytoolkit.googleapis.com/v1"

FIREBASE_ERROR_MESSAGES = {
    "EMAIL_EXISTS": ("El correo electrónico ya está en uso.", 409),
    "EMAIL_NOT_FOUND": ("Usuario no encontrado", 404),
    "INVALID_PASSWORD": ("Credenciales inválidas", 401),
    "INVALID_LOGIN_CREDENTIALS": ("Credenciales inválidas", 401),
    "USER_DISABLED": ("Usuario deshabilitado", 403),
    "TOO_MANY_ATTEMPTS_TRY_LATER": (
        "Demasiados intentos. Inténtelo más tarde",
        429
    )
}


class FederatedAuthError(Exception):
    def __init__(self, description, status_code=500):
        super().__init__(description)
        self.description = description
        self.status_code = status_code


def _get_firebase_api_key():
    return os.getenv("FIREBASE_WEB_API_KEY", "").strip()


def _get_auth_service_timeout():
    timeout = os.getenv("AUTH_SERVICE_TIMEOUT", "5").strip()

    try:
        return float(timeout)
    except ValueError:
        return 5.0


def _require_provider_config():
    if not _get_firebase_api_key():
        raise FederatedAuthError(
            "Proveedor de autenticacion externa no configurado",
            500
        )


def _build_url(path):
    _require_provider_config()
    return f"{FIREBASE_AUTH_BASE_URL}{path}?key={_get_firebase_api_key()}"


def _map_firebase_error(raw_body):
    default_message = "Error de autenticacion federada"
    default_status = 400

    if not raw_body:
        return default_message, default_status

    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body, default_status

    firebase_error = parsed.get("error", {})
    code = firebase_error.get("message", "")

    if code in FIREBASE_ERROR_MESSAGES:
        return FIREBASE_ERROR_MESSAGES[code]

    return default_message, default_status


def _post_json(path, payload):
    url = _build_url(path)

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with request.urlopen(req, timeout=_get_auth_service_timeout()) as response:
            raw_body = response.read().decode("utf-8")
            if not raw_body:
                return {}
            return json.loads(raw_body)

    except error.HTTPError as ex:
        raw_body = ex.read().decode("utf-8") if ex.fp else ""
        description, status_code = _map_firebase_error(raw_body)

        raise FederatedAuthError(description, status_code)

    except error.URLError:
        raise FederatedAuthError(
            "No fue posible conectar con Firebase Authentication",
            503
        )


def register_user(mail, contrasenia):
    response = _post_json("/accounts:signUp", {
        "email": mail,
        "password": contrasenia,
        "returnSecureToken": True
    })

    if response.get("localId") is None:
        raise FederatedAuthError(
            response.get("description", "No fue posible registrar el usuario"),
            400
        )

    return response


def authenticate_user(mail, contrasenia):
    response = _post_json("/accounts:signInWithPassword", {
        "email": mail,
        "password": contrasenia,
        "returnSecureToken": True
    })

    if response.get("localId") is None:
        raise FederatedAuthError(
            response.get("description", "Credenciales invalidas"),
            401
        )

    return response