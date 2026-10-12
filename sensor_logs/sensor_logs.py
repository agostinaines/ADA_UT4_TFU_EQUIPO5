from authentication.decorators import roles_required
from flask import Blueprint, jsonify
import sensor_logs.sensor_logs_repository as sensor_logs_repository

sensor_logs = Blueprint("sensor_logs", __name__)

@sensor_logs.route('/getAllLogs')
@roles_required("operador")
def get_all_logs_endpoint():
    try:
        logs = sensor_logs_repository.get_all_logs()

        return jsonify({
            'success': True,
            'logs': logs
        }), 200

    except Exception as ex:
        return jsonify({
            'success': False,
            'description': 'Internal server error',
        }), 500

@sensor_logs.route('/getAll/<id>/logs')
@roles_required("operador")
def get_all_sensor_logs_endpoint(id):
    try:
        logs = sensor_logs_repository.get_all_sensor_logs(id)

        return jsonify({
            'success': True,
            'logs': logs
        }), 200
    
    except Exception as ex:
        return jsonify({
            'success': False,
            'description': 'Internal server error',
        }), 500