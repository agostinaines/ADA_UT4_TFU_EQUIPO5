from common.db import get_connection


def register_citizen(mail, name, last_name):
    """Registra un ciudadano."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO usuario (mail, nombre, apellido) VALUES (%s, %s, %s)",
                (mail, name, last_name),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_mail(mail):
    """Verifica si el correo electrónico ya está registrado."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT mail FROM usuario WHERE mail = %s", (mail,))
            return cursor.fetchone() is not None
    finally:
        connection.close()


def get_role(mail):
    """Devuelve el rol del usuario (o None si no existe)."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT rol FROM usuario WHERE mail = %s", (mail,))
            result = cursor.fetchone()
            return result["rol"] if result is not None else None
    finally:
        connection.close()


def ping():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    finally:
        connection.close()
