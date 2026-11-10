"""Tests unitarios del Circuit Breaker / ServiceClient (sin red ni Docker)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests

from common.resilience import (CLOSED, HALF_OPEN, OPEN, CircuitBreaker, ServiceClient,
                               ServiceUnavailable)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def boom():
    raise requests.ConnectionError("down")


class CircuitBreakerTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=10, clock=self.clock)

    def test_opens_after_threshold_and_fails_fast(self):
        for _ in range(3):
            with self.assertRaises(requests.ConnectionError):
                self.cb.call(boom)
        self.assertEqual(self.cb.snapshot()["state"], OPEN)

        called = []
        with self.assertRaises(ServiceUnavailable) as ctx:
            self.cb.call(lambda: called.append(1))
        self.assertEqual(ctx.exception.reason, "circuit_open")
        self.assertEqual(called, [])  # no se tocó la red

    def test_half_open_probe_success_closes(self):
        for _ in range(3):
            with self.assertRaises(requests.ConnectionError):
                self.cb.call(boom)
        self.clock.t = 11
        self.assertEqual(self.cb.snapshot()["state"], HALF_OPEN)
        self.assertEqual(self.cb.call(lambda: "ok"), "ok")
        self.assertEqual(self.cb.snapshot()["state"], CLOSED)

    def test_half_open_probe_failure_reopens(self):
        for _ in range(3):
            with self.assertRaises(requests.ConnectionError):
                self.cb.call(boom)
        self.clock.t = 11
        with self.assertRaises(requests.ConnectionError):
            self.cb.call(boom)
        self.assertEqual(self.cb.snapshot()["state"], OPEN)

    def test_success_resets_failure_count(self):
        for _ in range(2):
            with self.assertRaises(requests.ConnectionError):
                self.cb.call(boom)
        self.cb.call(lambda: 1)
        for _ in range(2):
            with self.assertRaises(requests.ConnectionError):
                self.cb.call(boom)
        self.assertEqual(self.cb.snapshot()["state"], CLOSED)

    def test_client_errors_do_not_open(self):
        class ClientErr(Exception):
            ignore_for_breaker = True

        def bad():
            raise ClientErr()

        for _ in range(10):
            with self.assertRaises(ClientErr):
                self.cb.call(bad)
        self.assertEqual(self.cb.snapshot()["state"], CLOSED)


def resp(status):
    r = mock.Mock()
    r.status_code = status
    return r


class ServiceClientTests(unittest.TestCase):
    def make(self, **kw):
        return ServiceClient("svc", "http://x", retries=2, backoff=0, failure_threshold=2,
                             recovery_timeout=60, **kw)

    @mock.patch("common.resilience.requests.request")
    def test_get_is_retried_then_succeeds(self, req):
        req.side_effect = [requests.ConnectionError(), requests.Timeout(), resp(200)]
        self.assertEqual(self.make().request("GET", "/a").status_code, 200)
        self.assertEqual(req.call_count, 3)

    @mock.patch("common.resilience.requests.request")
    def test_post_is_not_retried(self, req):
        req.side_effect = requests.ConnectionError()
        with self.assertRaises(ServiceUnavailable) as ctx:
            self.make().request("POST", "/a")
        self.assertEqual(ctx.exception.reason, "unreachable")
        self.assertEqual(req.call_count, 1)

    @mock.patch("common.resilience.requests.request")
    def test_timeout_maps_to_reason(self, req):
        req.side_effect = requests.Timeout()
        with self.assertRaises(ServiceUnavailable) as ctx:
            self.make().request("POST", "/a")
        self.assertEqual(ctx.exception.reason, "timeout")

    @mock.patch("common.resilience.requests.request")
    def test_5xx_returned_but_counts_as_failure(self, req):
        req.return_value = resp(500)
        c = self.make()
        self.assertEqual(c.request("POST", "/a").status_code, 500)
        self.assertEqual(c.request("POST", "/a").status_code, 500)
        self.assertEqual(c.breaker.snapshot()["state"], OPEN)
        with self.assertRaises(ServiceUnavailable):
            c.request("POST", "/a")
        self.assertEqual(req.call_count, 2)  # la 3ª llamada ni salió a la red

    @mock.patch("common.resilience.requests.request")
    def test_4xx_does_not_count(self, req):
        req.return_value = resp(404)
        c = self.make()
        for _ in range(5):
            self.assertEqual(c.request("GET", "/a").status_code, 404)
        self.assertEqual(c.breaker.snapshot()["state"], CLOSED)


if __name__ == "__main__":
    unittest.main()
