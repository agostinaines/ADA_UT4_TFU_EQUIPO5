from common.db import get_connection


def ping():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    finally:
        connection.close()


def get_monthly_stats():
    """Lee la vista materializada (tabla precalculada)."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM monthly_region_stats")
            return [
                {
                    "region": r["region"],
                    "promedio": r["promedio"],
                    "minimo": r["minimo"],
                    "maximo": r["maximo"],
                    "cantidad_lecturas": r["cantidad_lecturas"],
                    "ultima_actualizacion": r["ultima_actualizacion"],
                }
                for r in cursor.fetchall()
            ]
    finally:
        connection.close()


def save_monthly_stats(rows):
    """Actualiza la vista materializada con el agregado que devolvió el sensor-service."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for r in rows:
                cursor.execute(
                    """
                    INSERT INTO monthly_region_stats
                        (region, promedio, minimo, maximo, cantidad_lecturas, ultima_actualizacion)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        promedio = VALUES(promedio),
                        minimo = VALUES(minimo),
                        maximo = VALUES(maximo),
                        cantidad_lecturas = VALUES(cantidad_lecturas),
                        ultima_actualizacion = VALUES(ultima_actualizacion)
                    """,
                    (r["region"], r["promedio"], r["minimo"], r["maximo"], r["cantidad_lecturas"]),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
