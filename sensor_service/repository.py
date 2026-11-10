import os
import time as tmodule
import uuid

from common.db import get_connection

REPAIR_SECONDS = int(os.getenv("REPAIR_SECONDS", "30"))

def create(version, region):
    """Crea un nuevo sensor."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO sensor (version, region) VALUES (%s, %s)",
                (version, region),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_all():
    """Devuelve todos los sensores registrados."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, activo, roto FROM sensor")
            return [
                {"id": row["id"], "activo": row["activo"], "roto": row["roto"]}
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def get_sensor(sensor_id):
    """Devuelve un sensor (id, activo, roto, region) o None si no existe."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, activo, roto, region FROM sensor WHERE id = %s", (sensor_id,)
            )
            return cursor.fetchone()
    finally:
        connection.close()


def load_active_sensors():
    """Sensores activos y no rotos (los usa la simulación de lecturas)."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, region FROM sensor WHERE activo = TRUE AND roto = FALSE"
            )
            return [{"id": row["id"], "region": row["region"]} for row in cursor.fetchall()]
    finally:
        connection.close()


def get_summary():
    """Conteo de sensores para el Health Endpoint Monitoring."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(CASE WHEN roto = FALSE THEN 1 ELSE 0 END), 0) AS activos,
                    COALESCE(SUM(CASE WHEN roto = TRUE THEN 1 ELSE 0 END), 0) AS rotos
                FROM sensor
                """
            )
            row = cursor.fetchone()
            return {
                "total": int(row["total"]),
                "activos": int(row["activos"]),
                "rotos": int(row["rotos"]),
            }
    finally:
        connection.close()


def mark_as_broken(sensor_id):
    """Marca un sensor como roto y lo apaga (idempotente)."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE sensor SET roto = TRUE, activo = FALSE WHERE id = %s",
                (sensor_id,),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def mark_as_fixed(sensor_id):
    """Repara un sensor; simula el tiempo que lleva repararlo (tarea tardía)."""
    tmodule.sleep(REPAIR_SECONDS)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE sensor SET roto = FALSE, activo = FALSE WHERE id = %s",
                (sensor_id,),
            )
        connection.commit()
        print(" ")
        print(f"SENSOR {sensor_id} REPARADO")
        print(" ")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_fixed(sensor_id):
    """
    Estado del 'ticket' de reparación (Asynchronous Request-Reply).
    Devuelve (estado, descripcion) con estado 'pending' o 'done', o None si el sensor no existe.
    """
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT roto FROM sensor WHERE id = %s", (sensor_id,))
            sensor = cursor.fetchone()

        if sensor is None:
            return None
        if sensor["roto"]:
            return "pending", "Su solicitud se sigue procesando"
        return "done", f"El sensor {sensor_id} fue reparado con éxito"
    finally:
        connection.close()


def toggle_sensor(sensor_id):
    """Activa o desactiva un sensor. Devuelve None si no existe."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT activo FROM sensor WHERE id = %s", (sensor_id,))
            sensor = cursor.fetchone()
            if sensor is None:
                return None

            if sensor["activo"]:
                cursor.execute("UPDATE sensor SET activo = FALSE WHERE id = %s", (sensor_id,))
                description = "Sensor apagado"
            else:
                cursor.execute("UPDATE sensor SET activo = TRUE WHERE id = %s", (sensor_id,))
                description = "Sensor prendido"

        connection.commit()
        return description
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def create_log(sensor_id, reading):
    """Inserta una lectura de un sensor."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO sensor_logs (sensor_id, lectura) VALUES (%s, %s)",
                (sensor_id, reading),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_all_logs():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, sensor_id, lectura FROM sensor_logs")
            return [
                {"id": r["id"], "sensor_id": r["sensor_id"], "lectura": r["lectura"]}
                for r in cursor.fetchall()
            ]
    finally:
        connection.close()


def get_all_sensor_logs(sensor_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, lectura FROM sensor_logs WHERE sensor_id = %s", (sensor_id,)
            )
            return [{"id": r["id"], "lectura": r["lectura"]} for r in cursor.fetchall()]
    finally:
        connection.close()


def aggregate_logs(days=30):
    """
    Agregado por región de las lecturas de los últimos `days` días.
    Lo consume el Statistics Service (GET /internal/logs/aggregate).
    """
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.region AS region,
                       AVG(l.lectura) AS promedio,
                       MIN(l.lectura) AS minimo,
                       MAX(l.lectura) AS maximo,
                       COUNT(*)       AS cantidad_lecturas
                FROM sensor_logs l
                JOIN sensor s ON s.id = l.sensor_id
                WHERE l.log_fecha >= NOW() - INTERVAL %s DAY
                GROUP BY s.region
                """,
                (int(days),),
            )
            return [
                {
                    "region": r["region"],
                    "promedio": float(r["promedio"]),
                    "minimo": float(r["minimo"]),
                    "maximo": float(r["maximo"]),
                    "cantidad_lecturas": int(r["cantidad_lecturas"]),
                }
                for r in cursor.fetchall()
            ]
    finally:
        connection.close()

def create_alert(sensor_id, reading):
    """Registra una alerta en estado 'pendiente' y devuelve su id (UUID)."""
    alert_id = str(uuid.uuid4())
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO alerta (id, sensor_id, lectura, estado) VALUES (%s, %s, %s, 'pendiente')",
                (alert_id, sensor_id, reading),
            )
        connection.commit()
        return alert_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def confirm_alert(alert_id):
    """
    Confirmación del Alert Service (paso 8 de la secuencia). Idempotente.
    Devuelve None si la alerta no existe, True si quedó confirmada.
    """
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT estado FROM alerta WHERE id = %s", (alert_id,))
            alert = cursor.fetchone()
            if alert is None:
                return None
            if alert["estado"] == "pendiente":
                cursor.execute(
                    "UPDATE alerta SET estado = 'confirmada', confirmada_en = NOW() WHERE id = %s",
                    (alert_id,),
                )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_all_alerts(limit=100):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, sensor_id, lectura, estado, fecha, confirmada_en "
                "FROM alerta ORDER BY fecha DESC LIMIT %s",
                (int(limit),),
            )
            return [
                {
                    "id": r["id"],
                    "sensor_id": r["sensor_id"],
                    "lectura": float(r["lectura"]),
                    "estado": r["estado"],
                    "fecha": r["fecha"].isoformat() if r["fecha"] else None,
                    "confirmada_en": r["confirmada_en"].isoformat() if r["confirmada_en"] else None,
                }
                for r in cursor.fetchall()
            ]
    finally:
        connection.close()
