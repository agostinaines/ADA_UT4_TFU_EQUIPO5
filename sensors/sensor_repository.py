from configdb import get_connection

def create(version):
    '''
    Permite crear un nuevo sensor.
    '''
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sensor (version)
                VALUES (%s)
                """,
                (version,)
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def get_all():
    '''
    Devuelve todos los sensores que están registrados en la base de datos.
    '''
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, activo, roto
                FROM sensor
            """)
            rows = cursor.fetchall()

            return [
                {
                    'id': row['id'],
                    'activo': row['activo'],
                    'roto': row['roto']
                }
                for row in rows
            ]
    finally:
        connection.close()

def load_active_sensors():
    """
    Consulta los sensores guardados en la base de datos y los devuelve.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            sql = "SELECT s.id FROM sensor s WHERE s.activo = TRUE AND s.roto = FALSE;"
            cursor.execute(sql)
            sensors = cursor.fetchall()

            sensorsFormatted = []
            for sensor in sensors:
                sensorsFormatted.append(sensor['id'])

    return sensorsFormatted

def mark_as_broken(sensor_id):
    '''
    Permite cambiar el estado de un sensor si este falla.
    '''
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sensor
                SET roto = TRUE,
                    activo = FALSE
                WHERE id = %s
                """,
                (sensor_id,)
            )

        connection.commit()

    except:
        connection.rollback()
        raise

    finally:
        connection.close()

def mark_as_fixed(sensor_id):
    '''
    Permite arreglar un sensor.
    '''
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sensor
                SET roto = FALSE,
                    activo = FALSE
                WHERE id = %s
                """,
                (sensor_id,)
            )

        connection.commit()

    except:
        connection.rollback()
        raise

    finally:
        connection.close()

def toggle_sensor(sensor_id):
    '''
    Permite activar o desactivar un sensor.
    '''
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
            "SELECT activo FROM sensor WHERE id = %s",
            (sensor_id,)
            )

            sensor = cursor.fetchone()

            isActive = sensor['activo']

            if isActive:
                cursor.execute(
                    "UPDATE sensor SET activo = FALSE WHERE id = %s",
                    (sensor_id,)
                )
                description = 'Sensor apagado'
            else:
                cursor.execute(
                    "UPDATE sensor SET activo = TRUE WHERE id = %s",
                    (sensor_id,)
                )
                description = 'Sensor prendido'

            connection.commit()

            return description
    except:
            connection.rollback()
            raise
    
    finally:
        connection.close()