from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt

def roles_required(*required_roles):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            role = claims.get("rol")

            if role not in required_roles:
                return jsonify({
                    "success": False,
                    "description": "Access denied"
                }), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator
