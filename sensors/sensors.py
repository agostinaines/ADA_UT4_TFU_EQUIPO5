from flask import Blueprint, jsonify, request
from authentication.decorators import roles_required
from . import sensor_repository
import time as tmodule

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
        tmodule.sleep(30)
        sensor_repository.mark_as_fixed(id)

        return jsonify({
            'success': True,
            'description': f'Sensor {id} reparado con éxito'
        }), 200
    
    except Exception as ex:
        return jsonify({
            'success': True,
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