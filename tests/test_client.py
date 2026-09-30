"""Pruebas sin red: se inyecta un `opener` falso."""

import hashlib
import hmac
import io
import json
import time
import unittest
import urllib.error

from verificar_curp import (
    VerificarCurpClient,
    VerificarCurpError,
    parse_webhook,
    verify_webhook_signature,
)

ANSWER = {
    "curp": "PEGJ850101HDFRRL04",
    "valida": True,
    "razon": None,
    "fechaNacimiento": "1985-01-01",
    "sexo": "H",
    "claveEntidad": "DF",
    "entidad": "Ciudad de México",
    "cotejo": "coincide",
    "cotejoCampos": {"nombres": "coincide"},
}


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._raw = json.dumps(body).encode("utf-8")

    def read(self):
        return self._raw

    def getcode(self):
        return self.status


def ok_opener(status, body):
    calls = []

    def opener(req, timeout):
        calls.append(req)
        return FakeResponse(status, body)

    opener.calls = calls
    return opener


def http_error_opener(status, body):
    def opener(req, timeout):
        fp = io.BytesIO(json.dumps(body).encode("utf-8"))
        raise urllib.error.HTTPError(req.full_url, status, "error", {}, fp)

    return opener


class ClientTests(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(VerificarCurpError):
            VerificarCurpClient("")

    def test_validate_posts_json_and_maps_response(self):
        opener = ok_opener(200, {"success": True, "data": ANSWER, "tokens_remaining": 9})
        client = VerificarCurpClient("curp_test", opener=opener)

        result = client.validate(
            "PEGJ850101HDFRRL04", persona={"nombres": "Julio", "segundoApellido": None}
        )
        self.assertEqual(result.data, ANSWER)
        self.assertEqual(result.tokens_remaining, 9)
        self.assertIsNone(result.verificacion)

        req = opener.calls[0]
        self.assertEqual(req.full_url, "https://verificarcurp.com/api/v1/curp")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("X-api-key"), "curp_test")
        self.assertTrue(req.get_header("User-agent").startswith("verificar-curp-python/"))
        # None segundoApellido must survive as null: it means "has none".
        self.assertEqual(
            json.loads(req.data),
            {"curp": "PEGJ850101HDFRRL04", "persona": {"nombres": "Julio", "segundoApellido": None}},
        )

    def test_validate_verificar_uses_api_field_names(self):
        verificacion = {"aceptada": True, "job_id": "clz1", "estado": "pendiente", "expires_at": "x"}
        opener = ok_opener(
            200, {"success": True, "data": ANSWER, "tokens_remaining": 8, "verificacion": verificacion}
        )
        client = VerificarCurpClient("k", opener=opener)
        result = client.validate(
            ANSWER["curp"],
            verificar=True,
            destination_id="dst_1",
            idempotency_key="cliente-1",
            reintentos={"activo": False},
        )
        self.assertEqual(result.verificacion, verificacion)
        self.assertEqual(
            json.loads(opener.calls[0].data),
            {
                "curp": ANSWER["curp"],
                "verificar": True,
                "destinationId": "dst_1",
                "idempotencyKey": "cliente-1",
                "reintentos": {"activo": False},
            },
        )

    def test_validate_rejects_bad_input_without_calling_api(self):
        opener = ok_opener(200, {})
        client = VerificarCurpClient("k", opener=opener)
        with self.assertRaises(VerificarCurpError) as ctx:
            client.validate(ANSWER["curp"], verificar=True)
        self.assertEqual(ctx.exception.code, "INVALID_INPUT")
        with self.assertRaises(VerificarCurpError):
            client.validate("  ")
        self.assertEqual(opener.calls, [])

    def test_api_error_maps_code_status_block_reason(self):
        client = VerificarCurpClient(
            "k",
            opener=http_error_opener(
                402,
                {
                    "success": False,
                    "error": "Saldo insuficiente",
                    "code": "INSUFFICIENT_TOKENS",
                    "block_reason": "auto_topup_failed",
                },
            ),
        )
        with self.assertRaises(VerificarCurpError) as ctx:
            client.validate(ANSWER["curp"])
        err = ctx.exception
        self.assertEqual((err.code, err.status, err.block_reason), ("INSUFFICIENT_TOKENS", 402, "auto_topup_failed"))
        self.assertEqual(err.message, "Saldo insuficiente")

    def test_get_verification_quotes_id_and_returns_valores(self):
        verificacion = {"job_id": "clz 1", "estado": "delivered", "valores_entregados": True}
        valores = {"estatus": "ACTIVA", "curp": ANSWER["curp"]}
        opener = ok_opener(200, {"success": True, "verificacion": verificacion, "valores": valores})
        client = VerificarCurpClient("k", opener=opener)
        result = client.get_verification("clz 1")
        self.assertEqual(result.verificacion, verificacion)
        self.assertEqual(result.valores, valores)
        self.assertEqual(
            opener.calls[0].full_url, "https://verificarcurp.com/api/v1/curp/verificacion/clz%201"
        )
        self.assertEqual(opener.calls[0].get_method(), "GET")

    def test_get_verification_without_valores(self):
        opener = ok_opener(200, {"success": True, "verificacion": {"estado": "pending"}})
        result = VerificarCurpClient("k", opener=opener).get_verification("clz1")
        self.assertIsNone(result.valores)

    def test_get_balance(self):
        opener = ok_opener(200, {"success": True, "balance": 42})
        client = VerificarCurpClient("k", opener=opener, base_url="http://x/api/v1/")
        self.assertEqual(client.get_balance(), 42)
        self.assertEqual(opener.calls[0].full_url, "http://x/api/v1/balance")

    def test_network_error_and_timeout(self):
        def refused(req, timeout):
            raise urllib.error.URLError(ConnectionRefusedError("refused"))

        def slow(req, timeout):
            raise TimeoutError()

        with self.assertRaises(VerificarCurpError) as ctx:
            VerificarCurpClient("k", opener=refused).get_balance()
        self.assertEqual(ctx.exception.code, "NETWORK_ERROR")
        with self.assertRaises(VerificarCurpError) as ctx:
            VerificarCurpClient("k", opener=slow).get_balance()
        self.assertEqual(ctx.exception.code, "TIMEOUT")


SECRET = "whsec_" + "ab" * 32
RAW = json.dumps({"version": "1", "event": "curp.verification.completed", "data": {"estatus": "ACTIVA"}})


def server_sign(secret, timestamp, raw_body):
    """Exactly what the server's signPayload() computes."""
    return "sha256=" + hmac.new(
        secret.encode(), f"{timestamp}.{raw_body}".encode(), hashlib.sha256
    ).hexdigest()


class WebhookTests(unittest.TestCase):
    TS = "1790000000"

    def test_accepts_what_the_server_signs(self):
        sig = server_sign(SECRET, self.TS, RAW)
        self.assertTrue(verify_webhook_signature(SECRET, RAW, sig, self.TS, now=1790000010))
        self.assertTrue(verify_webhook_signature(SECRET, RAW.encode(), sig, self.TS, now=1790000010))

    def test_rejects_tampering_wrong_secret_stale_and_missing(self):
        sig = server_sign(SECRET, self.TS, RAW)
        now = 1790000000
        self.assertFalse(verify_webhook_signature(SECRET, RAW.replace("ACTIVA", "BAJA"), sig, self.TS, now=now))
        self.assertFalse(verify_webhook_signature("whsec_other", RAW, sig, self.TS, now=now))
        self.assertFalse(verify_webhook_signature(SECRET, RAW, sig, "1790000001", now=now))
        self.assertFalse(verify_webhook_signature(SECRET, RAW, sig, self.TS, now=now + 301))
        self.assertTrue(verify_webhook_signature(SECRET, RAW, sig, self.TS, now=now + 301, tolerance_seconds=0))
        self.assertFalse(verify_webhook_signature(SECRET, RAW, None, self.TS, now=now))
        self.assertFalse(verify_webhook_signature(SECRET, RAW, "sha256=zz", self.TS, now=now))
        self.assertFalse(verify_webhook_signature(SECRET, RAW, sig, "abc", now=now))

    def test_parse_webhook(self):
        ts = str(int(time.time()))
        sig = server_sign(SECRET, ts, RAW)
        self.assertEqual(parse_webhook(SECRET, RAW, sig, ts)["data"]["estatus"], "ACTIVA")
        with self.assertRaises(VerificarCurpError) as ctx:
            parse_webhook("whsec_x", RAW, sig, ts)
        self.assertEqual(ctx.exception.code, "INVALID_SIGNATURE")


if __name__ == "__main__":
    unittest.main()
