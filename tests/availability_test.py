"""
Prueba de DISPONIBILIDAD / AISLAMIENTO DE FALLOS (atributo de calidad elegido para la UT5).

Escenario: se cae el sensor-service mientras el sistema está en uso.
Hipótesis: el gateway abre el circuito, responde 503 en milisegundos (en lugar de colgarse),
y los endpoints de los servicios que no dependen de él (estadísticas ya calculadas, monitoreo)
siguen respondiendo 200. Recalcular estadísticas (/insertMonthlyStats) sí depende del sensor-service
y debe fallar rápido con 503 gracias al Circuit Breaker del statistics-service.

Requiere el sistema levantado con `docker compose up --build`.

Uso:
    python tests/availability_test.py --token <JWT_operador>
    python tests/availability_test.py --mail operador@example.com --password '...'
    (agregar --auto para que el script ejecute `docker compose stop/start sensor-service`)

Para comparar con la arquitectura anterior (monolito UT4), correr el mismo escenario
cambiando --stop-cmd, p.ej. `docker compose stop backend`, y usar los endpoints del monolito.
"""
import argparse
import statistics
import subprocess
import sys
import time

import requests


def timed(session, url, headers, n):
    rows = []
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            r = session.get(url, headers=headers, timeout=15)
            rows.append((r.status_code, (time.perf_counter() - t0) * 1000, r.headers.get("Retry-After")))
        except requests.RequestException as exc:
            rows.append((type(exc).__name__, (time.perf_counter() - t0) * 1000, None))
    return rows


def summarize(label, rows):
    codes = {}
    for code, _, _ in rows:
        codes[code] = codes.get(code, 0) + 1
    lat = [ms for _, ms, _ in rows]
    print(f"  {label:<34} códigos={codes}  latencia ms: "
          f"mediana={statistics.median(lat):.1f} máx={max(lat):.1f}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:5000")
    p.add_argument("--token")
    p.add_argument("--mail")
    p.add_argument("--password")
    p.add_argument("--auto", action="store_true")
    p.add_argument("--stop-cmd", default="docker compose stop sensor-service")
    p.add_argument("--start-cmd", default="docker compose start sensor-service")
    p.add_argument("--recovery", type=float, default=15, help="CB_RECOVERY_TIMEOUT del gateway")
    a = p.parse_args()

    s = requests.Session()
    token = a.token
    if not token:
        r = s.post(f"{a.base}/login", json={"mail": a.mail, "contrasenia": a.password}, timeout=15)
        r.raise_for_status()
        token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    sensors, stats = f"{a.base}/allSensors", f"{a.base}/getMonthlyStats"
    recompute = f"{a.base}/insertMonthlyStats"

    print("\n[1] Línea base (todos los servicios arriba)")
    summarize("GET /allSensors (sensor-service)", timed(s, sensors, h, 20))
    summarize("GET /getMonthlyStats (statistics)", timed(s, stats, h, 20))

    print("\n[2] Se detiene el sensor-service")
    if a.auto:
        subprocess.run(a.stop_cmd.split(), check=True)
    else:
        input(f"    Ejecutá en otra terminal:  {a.stop_cmd}   y presioná Enter... ")

    first = timed(s, sensors, h, 3)
    after = timed(s, sensors, h, 20)
    print("  Primeras 3 llamadas (el breaker todavía está cerrado -> timeouts/reintentos):")
    summarize("GET /allSensors", first)
    print("  Siguientes 20 llamadas (circuito abierto -> falla rápida):")
    summarize("GET /allSensors", after)
    print(f"  Retry-After informado: {after[-1][2]}")
    print("  Servicios NO afectados:")
    summarize("GET /getMonthlyStats (statistics)", timed(s, stats, h, 20))
    print("  Servicio que depende del sensor-service (statistics -> sensor, con Circuit Breaker):")
    summarize("GET /insertMonthlyStats", timed(s, recompute, h, 6))
    m = s.get(f"{a.base}/monitoring", headers=h, timeout=15)
    print(f"  GET /monitoring -> {m.status_code} estado={m.json().get('status')} "
          f"breakers={m.json().get('circuit_breakers')}")

    print("\n[3] Se reinicia el sensor-service")
    if a.auto:
        subprocess.run(a.start_cmd.split(), check=True)
    else:
        input(f"    Ejecutá en otra terminal:  {a.start_cmd}   y presioná Enter... ")
    deadline = time.time() + 90
    recovered = None
    t0 = time.time()
    while time.time() < deadline:
        code = s.get(sensors, headers=h, timeout=15).status_code
        if code == 200:
            recovered = time.time() - t0
            break
        time.sleep(1)
    if recovered is None:
        print("  El sistema NO se recuperó en 90 s (revisar logs).")
        sys.exit(1)
    print(f"  /allSensors volvió a responder 200 a los {recovered:.1f} s del reinicio "
          f"(recovery_timeout del breaker = {a.recovery}s).")


if __name__ == "__main__":
    main()
