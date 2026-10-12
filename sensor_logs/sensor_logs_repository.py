from configdb import get_connection

def create_log(sensor_id, reading):
    """
    Inserta un nuevo registro de un sensor en específico.
    Este método no se corresponde con un endpoint.
    """
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sensor_logs
                (sensor_id, lectura)
                VALUES (%s, %s)
                """,
                (sensor_id, reading)
            )

        connection.commit()

    except:
        connection.rollback()
        raise

    finally:
        connection.close()

def get_all_logs():
    """
    Consigue todos los registros de todos los sensores.
    """
    connection = get_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM sensor_logs")
            results = cursor.fetchall()

            return [
                {
                    'id': row['id'],
                    'sensor_id': row['sensor_id'],
                    'lectura': row['lectura'] 
                }
                for row in results
            ]

    finally:
        connection.close()

def get_all_sensor_logs(sensor_id):
    """
    Consigue todos los registros de un sensor en específico.
    """
    connection = get_connection()
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT * 
                FROM sensor_logs sL 
                WHERE sL.sensor_id = %s""", 
                (sensor_id,)
            )

            results = cursor.fetchall()

            return [
                {
                    'id': row['id'],
                    'lectura': row['lectura'] 
                }
                for row in results
            ]

    finally:
        connection.close()