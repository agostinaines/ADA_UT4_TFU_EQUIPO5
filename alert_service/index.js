// Disponibilidad: el último id procesado se guarda en Redis, así que si el servicio se cae y vuelve, retoma desde donde quedó y no pierde las alertas publicadas mientras estuvo caído.

const http = require("http");
const { createClient } = require("redis");

const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";
const SENSOR_SERVICE_URL = (process.env.SENSOR_SERVICE_URL || "http://sensor-service:5002").replace(/\/$/, "");
const PORT = parseInt(process.env.PORT || "5005", 10);
const STREAM = "sensor_alerts";
const LAST_ID_KEY = "alert_service:last_id";
const MAX_ALERTS = 100;
const ACK_TIMEOUT_MS = 3000;

const redis = createClient({ url: REDIS_URL });
redis.on("error", (error) => {
  console.error("Error de Redis:", error.message);
});

const processed = [];
let pendingAcks = [];

async function sendAck(alertId) {
  const response = await fetch(`${SENSOR_SERVICE_URL}/internal/alerts/${alertId}/ack`, {
    method: "POST",
    signal: AbortSignal.timeout(ACK_TIMEOUT_MS),
  });
  if (!response.ok && response.status !== 404) {
    throw new Error(`HTTP ${response.status}`);
  }
}

async function flushPendingAcks() {
  const remaining = [];
  for (const alertId of pendingAcks) {
    try {
      await sendAck(alertId);
    } catch (error) {
      remaining.push(alertId);
    }
  }
  pendingAcks = remaining;
}

async function processAlert(alert) {
  console.log("\nALERTA");
  console.log("Evento:", alert.event);
  console.log("Sensor:", alert.sensor_id);
  console.log("Lectura:", alert.reading);
  console.log("Fecha:", alert.timestamp);
  console.log("\n");

  processed.push({ ...alert, procesada_en: new Date().toISOString() });
  if (processed.length > MAX_ALERTS) processed.shift();

  if (alert.alert_id) {
    try {
      await sendAck(alert.alert_id);
    } catch (error) {
      console.error(`No se pudo confirmar la alerta ${alert.alert_id} (${error.message}); se reintenta luego`);
      pendingAcks.push(alert.alert_id);
    }
  }
}

function startHttpServer() {
  const send = (res, status, body) => {
    res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(body));
  };

  http
    .createServer((req, res) => {
      const path = (req.url || "").split("?")[0];

      if (req.method === "GET" && path === "/health") {
        const healthy = redis.isReady;
        return send(res, healthy ? 200 : 503, {
          status: healthy ? "healthy" : "unhealthy",
          service: "alert-service",
          checks: {
            redis: healthy ? "conectado a Redis" : "sin conexión a Redis",
            alertas_procesadas: processed.length,
            confirmaciones_pendientes: pendingAcks.length,
          },
        });
      }

      if (req.method === "GET" && path === "/alerts") {
        return send(res, 200, { success: true, alerts: [...processed].reverse() });
      }

      return send(res, 404, { success: false, description: "Not found" });
    })
    .listen(PORT, "0.0.0.0", () => console.log(`Alert Service escuchando HTTP en :${PORT}`));
}

async function main() {
  startHttpServer();
  await redis.connect();

  console.log("Servicio de alertas conectado a Redis");
  console.log("Esperando nuevas alertas");

  let lastId = (await redis.get(LAST_ID_KEY)) || "0";

  while (true) {
    try {
      const messages = await redis.xRead([{ key: STREAM, id: lastId }], { BLOCK: 5000, COUNT: 10 });

      if (pendingAcks.length > 0) await flushPendingAcks();
      if (!messages) continue;

      for (const stream of messages) {
        for (const message of stream.messages) {
          try {
            await processAlert(JSON.parse(message.message.payload));
          } catch (error) {
            console.error("No se pudo interpretar la alerta:", error.message);
          }
          lastId = message.id;
          await redis.set(LAST_ID_KEY, lastId);
        }
      }
    } catch (error) {
      console.error("Error leyendo el stream:", error.message);
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
  }
}

main().catch((error) => {
  console.error("Error en el servicio de alertas:", error.message);
  process.exit(1);
});
