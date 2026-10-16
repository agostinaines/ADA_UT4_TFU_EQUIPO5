from flask import Blueprint, jsonify, request
from authentication.decorators import roles_required
from . import sensor_repository
from threading import Thread

sensors = Blueprint("sensors", __name__)

@sensors.route('/allSensors')
@roles_required("operador")
def get_all_sensors_endpoint():
    try:
        sensors = sensor_repository.get_all()

        return jsonify({
            'success': True,
            'sensors': sensors
        }), 200

    except Exception as ex:
        return jsonify({
            'success': False,
            'description': 'Internal server error'
        }), 500

@sensors.route('/sensorStatus')
@roles_required('valet')
def get_sensor_status_endpoint():
    try:
        sensors = sensor_repository.get_all()
        sensors_status = [
            {
                'id': sensor['id'],
                'estado': 'roto' if sensor['roto'] else 'saludable'
            }
            for sensor in sensors
        ]

        return jsonify({
            'success': True,
            'sensors': sensors_status
        }), 200

    except Exception:
        return jsonify({
            'success': False,
            'description': 'Internal server error'
        }), 500

@sensors.route('/newSensor', methods=['POST'])
@roles_required("operador")
def new_sensor_endpoint():
    try:
        body = request.get_json()

        version = body.get('version')

        if not version:
            return jsonify({
                'success': False,
                'description': 'Faltan datos obligatorios'
            }), 400

        sensor_repository.create(version)

        return jsonify({
            'success': True,
            'description': 'Nuevo sensor registrado'
        }), 201

    except Exception as ex:
        return jsonify({
            'success': False,
            'description': 'Error'
        }), 500

@sensors.route('/repairSensor/<id>', methods=['PATCH'])
@roles_required("operador")
def repair_sensor_endpoint(id):
    try:
        Thread(target=sensor_repository.mark_as_fixed, args=(id,)).start()

        return jsonify({
            'success': True,
            'description': f'Ticket para reparar sensor {id} enviado con éxito'
        }), 200
    
    except Exception as ex:
        return jsonify({
            'success': True,
            'description': 'Error'
        }), 500

@sensors.route('/ticket/<id>')
@roles_required('operador')
def check_ticket_status(id):
    try:
        description = sensor_repository.get_fixed(id)

        return jsonify({
            'success': True,
            'description': description
        }), 200
    
    except Exception as ex:
        return jsonify({
            'success': False,
            'description': 'Error'
        }), 500

@sensors.route('/toggleSensor/<id>', methods=['PATCH'])
@roles_required("operador")
def toggle_sensor_endpoint(id):
    try:
        description = sensor_repository.toggle_sensor(id)

        return jsonify({
            'success': True,
            'description': description
        }), 200
    
    except Exception as ex:
        return jsonify({
            'success': False,
            'description': 'Error'
        }), 500