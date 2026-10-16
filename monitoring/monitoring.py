
from flask import Blueprint, jsonify
from datetime import datetime, timezone
from time import perf_counter
from authentication.decorators import roles_required

import monitoring.monitoring_repository as monitoring_repository

monitoring = Blueprint("monitoring", __name__)


@monitoring.route("/monitoring")
@roles_required('operador')
def health_endpoint():
    start_time = perf_counter()

    checks = {}

    try:
        checks = monitoring_repository.get_health_status()

        status = "healthy"
        http_status = 200

    except Exception:
        status = "unhealthy"
        http_status = 503

        checks = {
            "database": "unhealthy"
        }

    response_time_ms = round(
        (perf_counter() - start_time) * 1000, 2
    )

    return jsonify({
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "response_time_ms": response_time_ms,
        "checks": checks
    }), http_status
