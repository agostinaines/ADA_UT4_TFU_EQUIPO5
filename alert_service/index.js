
const { createClient } = require("redis");

const redis = createClient({
  url: process.env.REDIS_URL || "redis://localhost:6379"
});

redis.on("error", (error) => {
  console.error("Error de Redis:", error.message);
});

async function main() {
  await redis.connect();

  console.log("Servicio de alertas conectado a Redis");
  console.log("Esperando nuevas alertas");

  let lastId = "$";

  while (true) {
    const messages = await redis.xRead(
      [{ key: "sensor_alerts", id: lastId }],
      { BLOCK: 0, COUNT: 10 }
    );

    if (!messages) continue;

    for (const stream of messages) {
      for (const message of stream.messages) {
        lastId = message.id;

        try {
          const alert = JSON.parse(message.message.payload);

          console.log("\nALERTA");
          console.log("Evento:", alert.event);
          console.log("Sensor:", alert.sensor_id);
          console.log("Lectura:", alert.reading);
          console.log("Fecha:", alert.timestamp);
          console.log("\n");
        } catch (error) {
          console.error("No se pudo interpretar la alerta:", error.message);
        }
      }
    }
  }
}

main().catch((error) => {
  console.error("Error en el servicio de alertas:", error.message);
  process.exit(1);
});
