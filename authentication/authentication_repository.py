from configdb import get_connection

def register_citizen(mail, name, last_name, password):
    """
    Registra un ciudadano.
    """
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO usuario (mail, nombre, apellido) 
                VALUES (%s, %s, %s)
                """, 
                (mail, name, last_name,)
            )

            cursor.execute("""
                INSERT INTO login (mail, contrasenia) 
                VALUES (%s, %s)
                """, 
                (mail, password.decode('utf-8'),)
            )

            connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def get_mail(mail):
    """
    Verifica si el correo electrónico ya está registrado.
    """
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT mail
                FROM usuario 
                WHERE mail = %s""", 
                (mail,)
            )

            if cursor.fetchone():
                return True

            return False
    finally:
        connection.close()

def get_password(mail):
    """
    Devuelve la contraseña almacenada para cierto correo.
    """
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT contrasenia 
                FROM login 
                WHERE mail = %s
                """, 
                (mail,)
            )

            return cursor.fetchone()
    finally:
        connection.close()

def get_role(mail):
    """
    Devuelve el rol del usuario.
    """
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT rol 
                FROM usuario 
                WHERE mail = %s""", 
                (mail,)
            )
    
            result = cursor.fetchone()

            if result is not None:
                return result['rol']
    
            return None
    finally:
        connection.close()
