import os
import pymysql
from dbutils.pooled_db import PooledDB

class DataBaseConfig:
    DEBUG = True
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_DB = os.getenv("MYSQL_DB", "tfu3")
    MYSQL_USER = os.getenv("MYSQL_USER", "ada2")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "reallyStrongPassword123!")

config = {
    "development": DataBaseConfig
}

credentials = config['development']

POOL = PooledDB(
    creator=pymysql,
    maxconnections=3,
    mincached=0,
    host=credentials.MYSQL_HOST,
    user=credentials.MYSQL_USER,
    password=credentials.MYSQL_PASSWORD,
    database=credentials.MYSQL_DB,
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

def get_connection():
    return POOL.connection()