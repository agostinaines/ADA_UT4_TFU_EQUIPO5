# ADA_UT5_TFU_EQUIPO5 – Sistema de detección de desastres (microservicios)

Sistema que recibe lecturas de sensores, detecta posibles situaciones de desastre natural y genera alertas.
Es la evolución del proyecto de la UT4 (monolito Flask) a una arquitectura de **microservicios**, tal como
se describe en el informe de la UT5 de *Análisis y Diseño de Aplicaciones II* (UCU).


## 1. Arquitectura


| Servicio | Carpeta | Tecnología | Puerto | Base de datos | Responsabilidad |
|----------|---------|------------|--------|---------------|-----------------|
| API Gateway | `gateway/` | Python/Flask | 5000 (**público**) | – | Punto de entrada, validación de JWT y roles, enrutamiento, Circuit Breaker |
| Authentication Service | `auth_service/` | Python/Flask | 5001 | `auth_db` | Registro, login (Firebase), emisión de JWT y Valet Key |
| Sensor Service | `sensor_service/` | Python/Flask | 5002 | `sensor_db` | Sensores, lecturas, detección de anomalías, publica el evento, SOAP, simulación |
| Statistics Service | `statistics_service/` | Python/Flask | 5003 | `statistics_db` | Estadísticas mensuales por región (vista materializada) |
| Monitoring Service | `monitoring_service/` | Python/Flask | 5004 | – | Health Endpoint Monitoring agregado |
| Alert Service | `alert_service/` | Node.js | 5005 | – | Consume alertas de Redis Streams, las procesa y las confirma |
| Messaging Bridge | `messaging_bridge/` | Node.js | – | – | Puente RabbitMQ (AMQP) → Redis Streams |

Infraestructura (contenedores): **MySQL 8** (un contenedor, tres bases y tres usuarios), **RabbitMQ 4** y **Redis 7**.

## 2. Herramientas que se utilizan

| Herramienta | Uso |
|---|---|
| Docker Compose | Levantar, detener y administrar los microservicios |
| Postman | Realizar todas las llamadas HTTP y SOAP a los endpoints del sistema |
| Firebase | Autenticación de usuarios |
| MySQL | Almacenamiento de sensores, lecturas, usuarios y estadísticas |
| RabbitMQ | Transporte de eventos de alertas |
| Redis Streams | Comunicación entre Messaging Bridge y Alert Service |
| Python | Ejecución de los tests unitarios y prueba automatizada de disponibilidad |


## 3. Requisitos

- **Docker Desktop** (con `docker compose`) para levantar el sistema.
- **Python 3.10 o superior** solo para correr los tests desde tu máquina (`pip install flask requests`).
- Un **proyecto de Firebase** con *Authentication → Método de acceso → Email/Password* habilitado y un usuario operador
  (`operador@example.com`) creado en Firebase.
- Acceso a Internet (el login consulta Firebase).

## 4. Configuración (`.env`)

1. Copiá `.env.example` como `.env` en la raíz del proyecto (donde está `docker-compose.yml`).
2. Completá las dos variables obligatorias.

| Variable | Obligatoria | Por defecto | Qué hace |
|----------|:-----------:|-------------|----------|
| `SECRET_KEY` | **Sí** | – | Clave con la que se **firman los JWT**. La usan el Authentication Service (firma) y el gateway (verifica). No es una contraseña que se escriba en ningún lado: elegí una cadena larga (32 caracteres o más). Si la cambiás, los tokens anteriores dejan de valer. |
| `FIREBASE_WEB_API_KEY` | **Sí** | – | Clave de API web de tu proyecto de Firebase (*Configuración del proyecto → General → Clave de API web*). Con un valor de ejemplo como `AIza...` el login falla. |
| `AUTH_SERVICE_TIMEOUT` | No | `5` | Timeout (s) de las llamadas a Firebase |
| `UPSTREAM_CONNECT_TIMEOUT` | No | `1` | Timeout de conexión (s) entre servicios |
| `UPSTREAM_READ_TIMEOUT` | No | `5` | Timeout de lectura (s) entre servicios |
| `UPSTREAM_RETRIES` | No | `2` | Reintentos (solo métodos idempotentes) |
| `CB_FAILURE_THRESHOLD` | No | `3` | Fallos consecutivos para abrir el Circuit Breaker |
| `CB_RECOVERY_TIMEOUT` | No | `15` | Segundos antes de probar de nuevo con el circuito abierto |
| `REPAIR_SECONDS` | No | `30` | Duración simulada de una reparación de sensor |
| `READING_INTERVAL_SECONDS` | No | `10` | Intervalo entre lecturas simuladas de los sensores |
| `DAMAGE_THRESHOLD` | No | `0.99` | Lectura a partir de la cual se considera sensor dañado |

Ejemplo mínimo de `.env`:

```dotenv
SECRET_KEY="tfu-federated-auth-2026-local-secret-key"
FIREBASE_WEB_API_KEY="AIzaSyDify6L7xueihHlkpbyQi1UD_W_bRkhBrc"
```

> **Importante:** el `.env` está en el `.gitignore` y **no debe subirse al repositorio**. En `.env.example` dejá solo valores de ejemplo (`AIza...`), nunca la clave real.

Las variables se leen **al crear los contenedores**. Si cambiás el `.env`, aplicalo con `docker compose up -d --force-recreate` (o indicando los servicios, por ejemplo `auth-service gateway`).

## 5. Cómo levantar el proyecto

Desde la carpeta del proyecto (donde está `docker-compose.yml`):

```bash
docker compose up --build
```

La primera vez tarda varios minutos (descarga imágenes y construye los servicios). El gateway espera a que todos los demás servicios estén sanos (`healthcheck`), así que el sistema está listo cuando `docker compose ps` muestra todos los contenedores como `healthy` y en los logs aparecen líneas `GET /health ... 200`.

**Si venís de una versión anterior (otro esquema de base de datos):** hay que bajar el contenedor y borrar la carpeta `mysql_data`:

```bash
docker compose down -v
```

Nombres de los servicios en el compose: `db`, `rabbitmq`, `redis`, `auth-service`, `sensor-service`, `statistics-service`, `monitoring-service`, `alert-service`, `gateway` y `messaging-bridge`.

Para comprobar que el gateway responde: abrí http://localhost:5000/health (debe devolver `{"service":"gateway","status":"healthy"}`).

## 6. Cómo usar el sistema (API)

Todo pasa por el gateway: `http://localhost:5000`. Hay dos roles con token JWT:

- **operador**: se obtiene con `POST /login` (usuario de prueba `operador@example.com`, que debe existir en Firebase). Dura lo que defina el JWT por defecto.
- **valet**: una *Valet Key* (acceso limitado, 30 minutos) que el operador genera con `POST /valetKey`. La usan los sensores y el consumidor SOAP.

Los endpoints protegidos requieren el header `Authorization: Bearer <token>`. Sin token: `401`. Con un rol incorrecto: `403`.
Si un servicio está caído o su circuito está abierto, el gateway responde `503` con un header `Retry-After`.

| Método y ruta | Rol | Servicio | Descripción |
|---------------|-----|----------|-------------|
| `GET /` , `GET /health` | público | gateway | Bienvenida / healthcheck |
| `POST /register` | público | auth | Alta de ciudadano. Body: `nombre`, `apellido`, `mail`, `contrasenia` (mínimo 9 caracteres), `confirmarContrasenia` |
| `POST /login` | público | auth | Body: `mail`, `contrasenia`. Devuelve `access_token` y `rol` |
| `POST /valetKey` | operador | auth | Genera la Valet Key (rol `valet`, 30 min) |
| `GET /allSensors` | operador | sensor | Lista de sensores (`id`, `activo`, `roto`) |
| `POST /newSensor` | operador | sensor | Body: `version` (ej. `1.13`) y `region` (`Norte`, `Sur`, `Este` u `Oeste`) |
| `PATCH /repairSensor/<id>` | operador | sensor | Pide reparar un sensor (**asíncrono**: `202 Accepted` + header `Location: /ticket/<id>`) |
| `GET /ticket/<id>` | operador | sensor | Estado de la reparación: `pending` o `done` |
| `PATCH /toggleSensor/<id>` | operador | sensor | Prende o apaga un sensor |
| `POST /readings` | valet | sensor | Un sensor envía una lectura. Body: `{"sensor_id": 1, "lectura": 0.42}` (entre 0 y 1) |
| `GET /getAllLogs` | operador | sensor | Todas las lecturas |
| `GET /getAll/<id>/logs` | operador | sensor | Lecturas de un sensor |
| `GET /allAlerts` | operador | sensor | Alertas generadas y su estado (`pendiente` → `confirmada`) |
| `GET /sensorStatus` | valet | gateway → sensor (SOAP) | Estado de los sensores (REST hacia el cliente, SOAP hacia el servicio) |
| `GET /soap/sensors.wsdl` | público | sensor | Contrato WSDL |
| `POST /soap/sensors` | valet | sensor | Endpoint SOAP (operación `GetSensorStatus`) |
| `GET /insertMonthlyStats` | operador | statistics | Recalcula las estadísticas (últimos 30 días) pidiendo el agregado al Sensor Service |
| `GET /getMonthlyStats` | operador | statistics | Lee las estadísticas ya calculadas por región |
| `GET /alerts` | operador | alert | Últimas alertas procesadas por el Alert Service |
| `GET /monitoring` | operador | monitoring | Estado agregado de todos los servicios y de sus Circuit Breakers |

El Sensor Service además **simula sensores**: cada `READING_INTERVAL_SECONDS` genera una lectura aleatoria (0 a 1) por
cada sensor activo. Una lectura mayor o igual a `DAMAGE_THRESHOLD` (0.99) marca el sensor como roto y dispara una alerta.

> **Importante:** En la misma carpeta del proyecto se encuentra la colección de postman donde se encuentra cada uno de los endpoints disponibles, este llamado como **'ADA UT5 TFU EQUIPO 5.postman_collection'**.

## 7. Probar el flujo de una alerta desde Postman

### Paso 1. Obtener el token del operador

Crear una petición:

- Método: `POST`
- URL: `{{baseUrl}}/login`
- Authorization: `No Auth`
- Body → `raw` → `JSON`

```json
{
    "mail": "operador@example.com",
    "contrasenia": "operadoroperadorson"
}
```

La respuesta debe contener el `access_token` y el rol del usuario.

Para guardar automáticamente el token, entrar en la pestaña **Scripts → Post-response** y agregar:

```javascript
const response = pm.response.json();

if (response.access_token) {
    pm.environment.set("operatorToken", response.access_token);
}
```

Así, Postman guarda el token automáticamente en la variable `operatorToken`.

### Paso 2. Generar una Valet Key

Crear otra petición:

- Método: `POST`
- URL: `{{baseUrl}}/valetKey`
- Authorization → Bearer Token: `{{operatorToken}}`

No requiere Body.

La respuesta devuelve un nuevo `access_token`, correspondiente al rol `valet`.

En **Scripts → Post-response**, agregar:

```javascript
const response = pm.response.json();

if (response.access_token) {
    pm.environment.set("valetToken", response.access_token);
}
```

Ahora tenemos los dos tokens guardados y podemos utilizarlos en las siguientes peticiones.

### Paso 3. Consultar los sensores disponibles

Crear una petición:

- Método: `GET`
- URL: `{{baseUrl}}/allSensors`
- Authorization → Bearer Token: `{{operatorToken}}`

La respuesta permite identificar un sensor activo (`activo = true` y `roto = false`).

Elegir el identificador de uno de esos sensores y actualizar la variable `sensorId` del Environment.

### Paso 4. Enviar una lectura anómala

Crear una petición:

- Método: `POST`
- URL: `{{baseUrl}}/readings`
- Authorization → Bearer Token: `{{valetToken}}`
- Body → `raw` → `JSON`

```json
{
    "sensor_id": 1,
    "lectura": 0.995
}
```

Una lectura de `0.995` supera el umbral de daño (`0.99`), por lo que el sistema debería detectar la anomalía y generar una alerta.

La respuesta esperada es `201 Created`.

### Paso 5. Comprobar que la alerta fue procesada

Realizar las siguientes peticiones utilizando el token del operador.

**Consultar las alertas procesadas por Alert Service:**

- Método: `GET`
- URL: `{{baseUrl}}/alerts`
- Authorization: Bearer Token `{{operatorToken}}`

**Consultar las alertas registradas en Sensor Service:**

- Método: `GET`
- URL: `{{baseUrl}}/allAlerts`
- Authorization: Bearer Token `{{operatorToken}}`

La alerta debería aparecer con estado `confirmada`.

**Consultar el estado de los servicios:**

- Método: `GET`
- URL: `{{baseUrl}}/monitoring`
- Authorization: Bearer Token `{{operatorToken}}`

### Qué tenés que ver en los logs

Ejecutar en una terminal:

```bash
docker compose logs -f sensor-service messaging-bridge alert-service
```

Deberían aparecer los siguientes eventos:

1. `sensor-service`: `SENSOR 1 DAÑADO` y `Alerta enviada a RabbitMQ: {...}`.
2. `messaging-bridge`: `Mensaje reenviado a Redis: {...}` (mismo `alert_id`).
3. `alert-service`: bloque `ALERTA` con evento, sensor, lectura y fecha.
4. `sensor-service`: `POST /internal/alerts/<alert_id>/ack ... 200`.

Además, `GET /allAlerts` debe mostrar esa alerta como `confirmada`.

Las respuestas de `POST /readings` pueden ser:

- `201`: lectura procesada.
- `404`: el sensor no existe.
- `409`: el sensor está apagado o roto.

### Los sensores se rompen solos: cómo repararlos

La simulación rompe sensores con el tiempo (cada lectura tiene 1 % de probabilidad de superar el umbral), y un sensor roto deja de leerse.

Para recuperarlo:

**1. Solicitar la reparación**

- Método: `PATCH`
- URL: `{{baseUrl}}/repairSensor/{{sensorId}}`
- Authorization: Bearer Token `{{operatorToken}}`

La respuesta esperada es `202 Accepted`.

El sistema devuelve un ticket de reparación. Si la respuesta incluye el header `Location`, contiene la ruta para consultar el estado del proceso.

**2. Consultar el estado de la reparación**

- Método: `GET`
- URL: `{{baseUrl}}/ticket/{{sensorId}}`
- Authorization: Bearer Token `{{operatorToken}}`

El estado pasa de `pending` a `done`.

**3. Volver a prender el sensor**

La reparación deja el sensor apagado, por lo que es necesario volver a prenderlo.

- Método: `PATCH`
- URL: `{{baseUrl}}/toggleSensor/{{sensorId}}`
- Authorization: Bearer Token `{{operatorToken}}`

Si preferís que la simulación no moleste durante una demo, poné `READING_INTERVAL_SECONDS="3600"` en el `.env` y aplicá con:

```bash
docker compose up -d --force-recreate sensor-service
```

De esta forma, las lecturas las enviás manualmente desde Postman mediante `POST /readings`.

### Estadísticas

Para trabajar con las estadísticas también utilizamos Postman.

**1. Recalcular las estadísticas**

- Método: `GET`
- URL: `{{baseUrl}}/insertMonthlyStats`
- Authorization: Bearer Token `{{operatorToken}}`

Esta operación solicita el agregado al Sensor Service y actualiza las estadísticas locales.

**2. Consultar las estadísticas**

- Método: `GET`
- URL: `{{baseUrl}}/getMonthlyStats`
- Authorization: Bearer Token `{{operatorToken}}`

Devuelve el promedio, mínimo, máximo y cantidad de lecturas por región.

Si dejaste el sistema andando un rato, ya hay lecturas acumuladas; si no, el resultado puede estar vacío.

---

## 8. SOAP

La operación `GET /sensorStatus` se migró de REST/JSON a SOAP/XML (`GetSensorStatus`).

- **Contrato:** `GET {{baseUrl}}/soap/sensors.wsdl`.
- **Endpoint:** `POST {{baseUrl}}/soap/sensors`.
- **Consumidor interno:** el gateway invoca el servicio SOAP desde `GET /sensorStatus` (`gateway/soap_client.py`); el cliente sigue usando REST.

### Consultar el WSDL desde Postman

Crear una petición:

- Método: `GET`
- URL: `{{baseUrl}}/soap/sensors.wsdl`
- Authorization: `No Auth`

La respuesta debe mostrar el contrato WSDL del servicio SOAP.

### Realizar una petición SOAP desde Postman

Crear una petición:

- Método: `POST`
- URL: `{{baseUrl}}/soap/sensors`
- Authorization → Bearer Token: `{{valetToken}}`

En **Headers**, agregar:

| Key | Value |
|---|---|
| `Content-Type` | `text/xml; charset=utf-8` |
| `SOAPAction` | `http://tfu.ucu.edu.uy/sensors/GetSensorStatus` |

En **Body → raw**, seleccionar XML y colocar:

```xml
<?xml version="1.0"?>
<soap:Envelope
    xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:tns="http://tfu.ucu.edu.uy/sensors">
    <soap:Body>
        <tns:GetSensorStatusRequest/>
    </soap:Body>
</soap:Envelope>
```

Enviar la petición.

La respuesta debe ser un XML SOAP con el estado de los sensores.

### Consultar el estado mediante REST → SOAP

También se puede probar la integración entre el Gateway y el Sensor Service.

Crear una petición:

- Método: `GET`
- URL: `{{baseUrl}}/sensorStatus`
- Authorization → Bearer Token: `{{valetToken}}`

Esta operación es especialmente importante porque permite comprobar que el Gateway recibe una petición REST, invoca internamente al servicio SOAP y devuelve el resultado al cliente.

La respuesta es una lista con los identificadores y estados de los sensores (`saludable` o `roto`).

Un `Fault` SOAP de tipo `Client` (XML inválido, operación desconocida) no abre el Circuit Breaker; uno de tipo `Server` sí cuenta como fallo.

---

## 10. Validación del atributo de calidad (disponibilidad)

**Atributo elegido:** disponibilidad (aislamiento de fallos).

**Escenario:** se cae el `sensor-service` mientras el sistema está en uso.

**Hipótesis:** el gateway abre el circuito y responde `503` en milisegundos en lugar de colgarse; los servicios que no dependen del Sensor Service (estadísticas ya calculadas, monitoreo) siguen respondiendo `200`; al volver, todo se recupera.

Con el sistema levantado, ejecutar desde la carpeta del proyecto:

```bash
python tests/availability_test.py --mail operador@example.com --password "operadoroperadorson" --auto
```

Esta prueba se mantiene como un script de Python porque no es una llamada individual a un endpoint, sino una prueba automatizada que detiene y vuelve a iniciar contenedores, mide tiempos de respuesta y compara los resultados.


El script mide, antes y después de la caída, los códigos y las latencias de:

- `/allSensors` (depende del Sensor Service).
- `/getMonthlyStats` (no depende de él).
- `/insertMonthlyStats` (depende, vía Circuit Breaker).

También mide cuánto tarda el sistema en recuperarse al reiniciar el servicio.
