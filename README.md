# ADA_UT3_TFU_EQUIPO5

Backend Flask para gestión de sensores con autenticación federada en Firebase.

## Puesta en marcha

1. Completar `.env` en la raíz del proyecto.
2. Iniciar Docker Desktop.
3. Levantar la aplicación:

```bash
docker compose up --build
```

## Variables necesarias

- Se usa Firebase Authentication como proveedor externo gratuito.
- Habilitar `Email/Password` en Firebase Authentication.
- Definir `FIREBASE_WEB_API_KEY` con la Web API Key del proyecto.
- Opcionalmente definir `AUTH_SERVICE_TIMEOUT`.
- Definir `SECRET_KEY` para los JWT internos de la API.

Ejemplo de `.env`:

```env
MYSQL_HOST="localhost"
MYSQL_DB="tfu3"
MYSQL_USER="ada2"
MYSQL_PASSWORD="reallyStrongPassword123!"
SECRET_KEY="una-clave-larga-local"
FIREBASE_WEB_API_KEY="AIza..."
AUTH_SERVICE_TIMEOUT="5"
```

## Firebase

1. Entrar a [Firebase Console](https://console.firebase.google.com/) con tu cuenta de Google.
2. Crear o abrir el proyecto correspondiente.
3. Ir a `Authentication` -> `Get started`.
4. En `Sign-in method`, habilitar `Email/Password`.
5. Ir a `Project settings` -> `General`.
6. Copiar la `Web API Key`.

## Flujo de autenticación

- `/register`: crea el usuario en Firebase y registra el ciudadano en la API.
- `/login`: valida credenciales contra Firebase y devuelve un JWT interno con rol.
- `/valetKey`: requiere JWT de operador y devuelve un JWT interno con rol `valet`.
- `/sensorStatus`: requiere JWT `valet` y devuelve solo `id` y `estado` de los sensores.

## Verificación realizada

- Se validó el alta de usuario en Firebase.
- Se validó el login federado del operador.
- Se validó la emisión de `valetKey`.
- Se validó el acceso de la `valetKey` a `/sensorStatus`.
