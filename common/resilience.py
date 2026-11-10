"""
Resiliencia para la comunicación entre servicios (patrones Circuit Breaker, Retry y Timeout).

Aborda dos falacias de la computación distribuida:
  1. "La red es confiable"  -> timeouts + reintentos acotados + Circuit Breaker.
  2. "La latencia es cero"  -> timeouts explícitos y "fallar rápido" con el circuito abierto.

Estados del Circuit Breaker:
  CLOSED    : las llamadas pasan; se cuentan los fallos consecutivos.
  OPEN      : se rechazan las llamadas sin tocar la red (falla rápida) hasta que
              pasa `recovery_timeout`.
  HALF_OPEN : se deja pasar UNA llamada de prueba; si sale bien se cierra, si
              falla se vuelve a abrir.
"""
import math
import threading
import time

import requests

CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"
IDEMPOTENT_METHODS = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}


class ServiceUnavailable(Exception):
    """El servicio destino no pudo atenderse (circuito abierto, timeout o red caída)."""

    def __init__(self, service, reason, retry_after=0):
        super().__init__(f"{service}: {reason}")
        self.service = service
        self.reason = reason
        self.retry_after = retry_after


class _UpstreamServerError(Exception):
    """Respuesta 5xx del servicio: cuenta como fallo para el breaker."""


class CircuitBreaker:
    def __init__(self, name, failure_threshold=3, recovery_timeout=15.0, clock=time.monotonic):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._clock = clock
        self._lock = threading.Lock()
        self._state = CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._probe_in_flight = False

    def snapshot(self):
        with self._lock:
            state = self._state
            if state == OPEN and self._clock() - self._opened_at >= self.recovery_timeout:
                state = HALF_OPEN
            return {"state": state, "failures": self._failures}

    def _acquire(self):
        with self._lock:
            if self._state == OPEN:
                elapsed = self._clock() - self._opened_at
                if elapsed < self.recovery_timeout:
                    raise ServiceUnavailable(
                        self.name, "circuit_open",
                        retry_after=max(1, math.ceil(self.recovery_timeout - elapsed)),
                    )
                self._state = HALF_OPEN
                self._probe_in_flight = False
            if self._state == HALF_OPEN:
                if self._probe_in_flight:
                    raise ServiceUnavailable(self.name, "circuit_open", retry_after=1)
                self._probe_in_flight = True

    def _on_success(self):
        with self._lock:
            self._state = CLOSED
            self._failures = 0
            self._probe_in_flight = False

    def _on_failure(self):
        with self._lock:
            if self._state == HALF_OPEN:
                self._open()
            else:
                self._failures += 1
                if self._failures >= self.failure_threshold:
                    self._open()

    def _open(self):
        self._state = OPEN
        self._opened_at = self._clock()
        self._probe_in_flight = False

    def call(self, fn):
        self._acquire()
        try:
            result = fn()
        except Exception as exc:
            if getattr(exc, "ignore_for_breaker", False):
                self._on_success()
            else:
                self._on_failure()
            raise
        self._on_success()
        return result


class ServiceClient:
    """Cliente HTTP hacia otro microservicio, protegido por timeout, retry y circuit breaker."""

    def __init__(self, name, base_url, timeout=(1.0, 5.0), retries=2, backoff=0.2,
                 failure_threshold=3, recovery_timeout=15.0):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.breaker = CircuitBreaker(name, failure_threshold, recovery_timeout)

    def guard(self, fn):
        """Ejecuta `fn` bajo el breaker y traduce errores de red a ServiceUnavailable."""
        try:
            return self.breaker.call(fn)
        except requests.Timeout:
            raise ServiceUnavailable(self.name, "timeout")
        except requests.ConnectionError:
            raise ServiceUnavailable(self.name, "unreachable")

    def request(self, method, path, **kwargs):
        """
        Devuelve siempre la respuesta HTTP del servicio (incluso 4xx/5xx), salvo que
        no sea alcanzable: en ese caso lanza ServiceUnavailable. Las respuestas 5xx
        cuentan como fallo para el breaker. Solo se reintentan métodos idempotentes
        y solo ante errores de red/timeout.
        """
        url = self.base_url + path
        kwargs.setdefault("timeout", self.timeout)
        attempts = 1 + (self.retries if method.upper() in IDEMPOTENT_METHODS else 0)
        holder = {}

        def do():
            for i in range(attempts):
                try:
                    resp = requests.request(method, url, **kwargs)
                except (requests.ConnectionError, requests.Timeout):
                    if i < attempts - 1:
                        time.sleep(self.backoff * (2 ** i))
                        continue
                    raise
                holder["resp"] = resp
                if resp.status_code >= 500:
                    raise _UpstreamServerError(resp.status_code)
                return resp

        try:
            return self.guard(do)
        except _UpstreamServerError:
            return holder["resp"]
