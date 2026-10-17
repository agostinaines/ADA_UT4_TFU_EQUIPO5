
const amqp = require("amqplib");
const { createClient } = require("redis");

const RABBITMQ_URL =
  process.env.RABBITMQ_URL || "amqp://localhost:5672";

const REDIS_URL =
  process.env.REDIS_URL || "redis://localhost:6379";

const EXCHANGE = "sensor_alerts";
const QUEUE = "sensor_alerts_bridge";
const STREAM = "sensor_alerts";

async function main() {
  const redis = createClient({ url: REDIS_URL });

  redis.on("error", (error) => {
    console.error("Error de Redis:", error.message);
  });

  await redis.connect();

  const connection = await amqp.connect(RABBITMQ_URL);
  const channel = await connection.createChannel();

  await channel.assertExchange(EXCHANGE, "fanout", {
    durable: true
  });

  await channel.assertQueue(QUEUE, {
    durable: true
  });

  await channel.bindQueue(QUEUE, EXCHANGE, "");

  channel.prefetch(1);

  console.log("Messaging Bridge iniciado.");
  console.log("Origen: RabbitMQ");
  console.log("Destino: Redis Streams");
  console.log("Esperando mensajes");

  channel.consume(
    QUEUE,
    async (message) => {
      if (!message) return;

      try {
        const payload = message.content.toString();

        // Texto JSON.
        await redis.xAdd(STREAM, "*", {
          payload: payload
        });

        console.log("Mensaje reenviado a Redis:", payload);

        // Se confirma el mensaje solo despues de guardarlo
        channel.ack(message);
      } catch (error) {
        console.error("Error reenviando el mensaje:", error.message);

        // El mensaje vuelve a la cola para intentar procesarlo de nuevo
        channel.nack(message, false, true);
      }
    },
    { noAck: false }
  );

  connection.on("error", (error) => {
    console.error("Error de RabbitMQ:", error.message);
  });
}

main().catch((error) => {
  console.error("No se pudo iniciar el Messaging Bridge:", error.message);
  process.exit(1);
});
