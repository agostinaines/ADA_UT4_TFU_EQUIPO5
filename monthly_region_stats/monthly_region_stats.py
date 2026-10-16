from authentication.decorators import roles_required
from flask import Blueprint, jsonify
import monthly_region_stats.monthly_region_stats_repository as monthly_region_stats_repository

monthly_region_stats = Blueprint("monthly_region_stats", __name__)

@monthly_region_stats.route('/getMonthlyStats')
@roles_required("operador")
def get_monthly_stats():
    try:
        stats = monthly_region_stats_repository.get_monthly_stats()

        return jsonify({
            'success': True,
            'logs': stats
        }), 200

    except Exception as ex:
        return jsonify({
            'success': False,
            'description': 'Internal server error',
        }), 500

@monthly_region_stats.route('/insertMonthlyStats')
@roles_required("operador")
def insert_monthly_stats():
    try:
        monthly_region_stats_repository.post_monthly_stats()

        return jsonify({
            'success': True,
        }), 200

    except Exception as ex:
        return jsonify({
            'success': False,
            'description': 'Internal server error',
        }), 500