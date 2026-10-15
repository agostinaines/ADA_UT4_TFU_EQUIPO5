
from configdb import get_connection


def get_health_status():
    """
    Comprueba la conexión con la base de datos
    y obtiene el estado de los sensores.
    """
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

            cursor.execute("""
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(CASE
                        WHEN roto = FALSE THEN 1
                        ELSE 0
                    END), 0) AS activos,
                    COALESCE(SUM(CASE
                        WHEN roto = TRUE THEN 1
                        ELSE 0
                    END), 0) AS rotos
                FROM sensor
            """)

            result = cursor.fetchone()

            return {
                "database": "conectado a la base de datos",
                "sensores": {
                    "total": result["total"],
                    "activos": result["activos"],
                    "rotos": result["rotos"]
                }
            }

    finally:
        connection.close()
