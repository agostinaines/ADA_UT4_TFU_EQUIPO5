from configdb import get_connection

def get_monthly_stats():
    """
    Consigue todas las estadísticas mensuales de la base de datos.
    """
    connection = get_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM monthly_region_stats")
            results = cursor.fetchall()

            return [
                {
                    'region': row['region'],
                    'promedio': row['promedio'],
                    'minimo': row['minimo'],
                    'maximo': row['maximo'],
                    'cantidad_lecturas': row['cantidad_lecturas'],
                    'ultima_actualizacion': row['ultima_actualizacion']
                }
                for row in results
            ]

    finally:
        connection.close()

def post_monthly_stats():
    """
    Inserta las estadísticas mensuales en la base de datos.
    """
    connection = get_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
            """
                INSERT INTO monthly_region_stats (region, promedio, minimo, maximo, cantidad_lecturas, ultima_actualizacion)
                SELECT s.region, AVG(l.lectura), MIN(l.lectura), MAX(l.lectura), COUNT(*), NOW()
                FROM sensor_logs l
                JOIN sensor s ON s.id = l.sensor_id
                WHERE l.log_fecha >= NOW() - INTERVAL 30 DAY
                GROUP BY s.region
                ON DUPLICATE KEY UPDATE
                    promedio = VALUES(promedio),
                    minimo = VALUES(minimo),
                    maximo = VALUES(maximo),
                    cantidad_lecturas = VALUES(cantidad_lecturas),
                    ultima_actualizacion = VALUES(ultima_actualizacion)
                """
            )

            connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()