"""
Acceso a base de datos compartido por los microservicios.

Cada servicio tiene SU PROPIA base de datos (database per service): lo único que
comparten es este helper, que arma un pool de conexiones a partir de variables
de entorno (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD) distintas para cada servicio.
"""
import os
import threading

_pool = None
_lock = threading.Lock()


def _create_pool():
    import pymysql
    from dbutils.pooled_db import PooledDB

    return PooledDB(
        creator=pymysql,
        maxconnections=int(os.getenv("DB_MAX_CONNECTIONS", "5")),
        blocking=True,
        mincached=0,
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", ""),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_connection():
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                _pool = _create_pool()
    return _pool.connection()
