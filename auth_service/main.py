"""
auth-service: identidad y emisión de tokens.

Responsabilidades (extraídas del monolito, módulo `authentication`):
  - POST /register   : alta de ciudadano (Federated Identity -> Firebase + tabla usuario)
  - POST /login      : valida contra Firebase y emite el JWT interno con rol
  - POST /valetKey   : emite la Valet Key (JWT de 30 min, rol 'valet')
  - GET  /health     : Health Endpoint Monitoring de este servicio

Este servicio NO se publica al exterior: solo es alcanzable por el gateway dentro de la
red de Docker. El control de acceso por rol (operador) lo aplica el gateway.
"""
from dotenv import load_dotenv

load_dotenv()

import os
from datetime import timedelta

from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token

import federated_identity
import repository

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["JSON_AS_ASCII"] = False
JWTManager(app)


@app.route("/register", methods=["POST"])
def register_endpoint():
    try:
        body = request.get_json()

        nombre = body.get("nombre")
        apellido = body.get("apellido")
        mail = body.get("mail")
        contrasenia = body.get("contrasenia")
        confirmar = body.get("confirmarContrasenia")

        if not all([nombre, apellido, mail, contrasenia, confirmar]):
            return jsonify({"success": False, "description": "Faltan datos obligatorios"}), 400

        nombre = nombre.replace(" ", "")
        apellido = apellido.replace(" ", "")

        if contrasenia != confirmar:
            return jsonify({"success": False, "description": "Las contraseñas deben coincidir"}), 400

        if len(contrasenia) <= 8:
            return jsonify({"success": False,
                            "description": "La contraseña debe ser de un mínimo de 9 caracteres"}), 400

        if len(nombre) < 3 or not nombre.isalpha():
            return jsonify({"success": False, "description": "Formato de nombre inválido"}), 400

        if len(apellido) < 3 or not apellido.isalpha():
            return jsonify({"success": False, "description": "Formato de apellido inválido"}), 400

        if repository.get_mail(mail):
            return jsonify({"success": False, "description": "El correo electrónico ya está en uso."}), 409

        federated_identity.register_user(mail, contrasenia)
        repository.register_citizen(mail, nombre, apellido)

        return jsonify({"success": True, "description": "Usuario registrado correctamente."}), 201

    except federated_identity.FederatedAuthError as ex:
        return jsonify({"success": False, "description": ex.description}), ex.status_code
    except Exception:
        return jsonify({"success": False, "description": "Internal server error"}), 500


@app.route("/login", methods=["POST"])
def login_endpoint():
    try:
        body = request.get_json()
        mail = body.get("mail")
        contrasenia = body.get("contrasenia")

        if not mail or not contrasenia:
            return jsonify({"success": False, "description": "Faltan email o contraseña"}), 400

        federated_identity.authenticate_user(mail, contrasenia)

        rol = repository.get_role(mail)
        if rol is None:
            return jsonify({"success": False, "description": "Rol no encontrado"}), 500

        access_token = create_access_token(identity=mail, additional_claims={"rol": rol})

        return jsonify({"success": True, "access_token": access_token, "rol": rol}), 200

    except federated_identity.FederatedAuthError as ex:
        return jsonify({"success": False, "description": ex.description}), ex.status_code
    except Exception:
        return jsonify({"success": False, "description": "Internal server error"}), 500


@app.route("/valetKey", methods=["POST"])
def generate_valet_key_endpoint():
    try:
        valet_token = create_access_token(
            identity="valet",
            additional_claims={"rol": "valet"},
            expires_delta=timedelta(minutes=30),
        )
        return jsonify({"success": True, "access_token": valet_token, "rol": "valet"}), 200
    except Exception:
        return jsonify({"success": False, "description": "Internal server error"}), 500


@app.route("/health")
def health():
    try:
        repository.ping()
        return jsonify({
            "status": "healthy",
            "service": "auth-service",
            "checks": {"database": "conectado a la base de datos"},
        }), 200
    except Exception:
        return jsonify({
            "status": "unhealthy",
            "service": "auth-service",
            "checks": {"database": "unhealthy"},
        }), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
