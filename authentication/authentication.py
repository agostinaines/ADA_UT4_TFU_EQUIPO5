from flask import Blueprint, request, jsonify
import authentication.authentication_repository as authentication_repository
from flask_jwt_extended import create_access_token
import bcrypt
from datetime import datetime, timedelta, timezone
import os

SECRET_KEY = os.getenv("SECRET_KEY", "faltaSecretKey!")

authentication = Blueprint('authentication', __name__)

@authentication.route('/register', methods=['POST'])
def register_endpoint():
    try:
        body = request.get_json()

        nombre = body.get('nombre')
        apellido = body.get('apellido')
        mail = body.get('mail')
        contrasenia = body.get('contrasenia')
        confirmarContrasenia = body.get('confirmarContrasenia')

        if not all([nombre, apellido, mail, contrasenia, confirmarContrasenia]):
            return jsonify({
                'success': False,
                'description': 'Faltan datos obligatorios'
            }), 400

        nombre = nombre.replace(' ', '')
        apellido = apellido.replace(' ', '')

        if contrasenia != confirmarContrasenia:
            return jsonify({
                'success': False,
                'description': 'Las contraseñas deben coincidir'
            }), 400

        if len(contrasenia) <= 8:
            return jsonify({
                'success': False,
                'description': 'La contraseña debe ser de un mínimo de 9 caracteres'
            }), 400

        if len(nombre) < 3 or not nombre.isalpha():
            return jsonify({
                'success': False,
                'description': 'Formato de nombre inválido'
            }), 400

        if len(apellido) < 3 or not apellido.isalpha():
            return jsonify({
                'success': False,
                'description': 'Formato de apellido inválido'
            }), 400

        already_exists = authentication_repository.get_mail(mail)

        if already_exists:
            return jsonify({
                'success': False,
                'description': 'El correo electrónico ya está en uso.'
            }), 409

        hash_pwd = bcrypt.hashpw(
            contrasenia.encode('utf-8'),
            bcrypt.gensalt()
        )
            
        authentication_repository.register_citizen(mail, nombre, apellido, hash_pwd)
        
        return jsonify({
            'success': True,
            'description': 'Usuario registrado correctamente.'
        }), 201
    
    except Exception as ex:
        return jsonify({
            'success': False,
            'description': 'Internal server error',
        }), 500

@authentication.route('/login', methods=['POST'])
def login_endpoint():
    try:
        body = request.get_json()
        mail = body.get('mail')
        contrasenia = body.get('contrasenia')

        if not mail or not contrasenia:
            return jsonify({
                'success': False,
                'description': 'Faltan email o contraseña'
            }), 400

        already_exists = authentication_repository.get_mail(mail)

        if not already_exists:
            return jsonify({
                    "success": False,
                    "description": "Usuario no encontrado"
                }), 404

        password_exists = authentication_repository.get_password(mail)

        if password_exists is None:
            return jsonify({
                'success': False, 
                'description': 'Credenciales inválidas'
            }), 401

        stored_password = password_exists['contrasenia']
        stored_password.encode('utf-8')
        if isinstance(stored_password, str):
            stored_password = stored_password.encode('utf-8')
        input_password_bytes = contrasenia.encode('utf-8')
        result = bcrypt.checkpw(input_password_bytes, stored_password)

        if not result:
            return jsonify({
                'success': False, 
                'description': 'Credenciales inválidas'
            }), 401

        rol = authentication_repository.get_role(mail)

        if rol == None:
            return jsonify({
                'success': False,
                'description': 'Rol no encontrado'
            }), 500

        now = datetime.now(timezone.utc)
        access_payload = {
            'mail': mail,
            'rol': rol,
            'exp': now + timedelta(minutes=120)
        }

        access_token = create_access_token(
        identity=mail,
        additional_claims={
            "rol": rol
            }
        )

        return jsonify({
            'success': True,
            'access_token': access_token,
            'rol': rol
        }), 200
    
    except Exception as ex:
        return jsonify({
            'success': False,
            'description': 'Internal server error'
        }), 500
