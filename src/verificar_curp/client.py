"""Cliente HTTP para la API de Verificar CURP (sin dependencias externas)."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

from .errors import VerificarCurpError
from .types import CaptureLink, Persona, Reintentos, ValidateResult, VerificationStatusResult

DEFAULT_BASE_URL = "https://verificarcurp.com/api/v1"
DEFAULT_TIMEOUT = 30.0
# Cloudflare, in front of the API, answers 403 to urllib's default
# "Python-urllib/3.x" User-Agent, so every request names the SDK instead.
USER_AGENT = "verificar-curp-python/1.1.0"

# Firma de un "opener" inyectable (para tests): recibe un Request y un timeout
# y devuelve un objeto con .status / .getcode() y .read(), o lanza HTTPError.
Opener = Callable[[urllib.request.Request, float], Any]


class VerificarCurpClient:
    """Cliente para la API de Verificar CURP.

    Ejemplo::

        from verificar_curp import VerificarCurpClient

        client = VerificarCurpClient(api_key="curp_tu_api_key")
        result = client.validate(
            "PEGJ850101HDFRRL04",
            persona={"nombres": "Julio", "fechaNacimiento": "1985-01-01"},
        )
        print(result.data["valida"], result.data["cotejo"])

    https://verificarcurp.com/docs
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        opener: Optional[Opener] = None,
    ) -> None:
        if not api_key:
            raise VerificarCurpError("Falta `api_key`.", "INVALID_INPUT")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener: Opener = opener or (
            lambda req, timeout: urllib.request.urlopen(req, timeout=timeout)
        )

    def validate(
        self,
        curp: str,
        *,
        persona: Optional[Persona] = None,
        verificar: bool = False,
        destination_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        reintentos: Optional[Reintentos] = None,
    ) -> ValidateResult:
        """Valida la estructura de una CURP y, con ``persona``, la coteja.

        Con ``verificar=True`` la verifica además en el registro RENAPO: la
        respuesta trae ``verificacion`` al instante y el resultado del registro
        llega a ``destination_id`` por separado.

        Una CURP mal formada NO es un error: ``data["valida"]`` es False y el
        motivo va en ``data["razon"]``.

        Lanza :class:`VerificarCurpError` ante saldo insuficiente, destino
        inexistente, petición inválida, error de red, timeout, etc.
        """
        if not isinstance(curp, str) or not curp.strip():
            raise VerificarCurpError("Falta la CURP (`curp`).", "INVALID_INPUT")
        if verificar and not destination_id:
            raise VerificarCurpError(
                "`destination_id` es obligatorio con `verificar=True`.", "INVALID_INPUT"
            )

        payload: dict = {"curp": curp}
        if persona is not None:
            payload["persona"] = persona
        if verificar:
            payload["verificar"] = True
        if destination_id is not None:
            payload["destinationId"] = destination_id
        if idempotency_key is not None:
            payload["idempotencyKey"] = idempotency_key
        if reintentos is not None:
            payload["reintentos"] = reintentos

        body = self._request("POST", "/curp", json_body=payload)
        return ValidateResult(
            data=body["data"],
            tokens_remaining=body["tokens_remaining"],
            verificacion=body.get("verificacion"),
        )

    def get_verification(self, job_id: str) -> VerificationStatusResult:
        """Consulta el estado de una verificación (sin costo).

        Si el resultado del registro sigue guardado, llega en ``valores`` UNA
        sola vez y se borra en la misma operación. Si tu destino ya lo recibió,
        solo verás el estado: esta consulta es la forma de recuperarlo cuando
        la entrega a tu destino falló.

        Lanza :class:`VerificarCurpError` con ``NOT_FOUND`` si la verificación
        no es de tu cuenta.
        """
        if not job_id:
            raise VerificarCurpError("Falta el `job_id`.", "INVALID_INPUT")
        body = self._request("GET", "/curp/verificacion/" + urllib.parse.quote(job_id, safe=""))
        return VerificationStatusResult(
            verificacion=body["verificacion"], valores=body.get("valores")
        )

    def get_balance(self) -> int:
        """Consulta el saldo de tokens de tu cuenta."""
        body = self._request("GET", "/balance")
        return int(body["balance"])

    def create_capture_link(
        self,
        destination_id: str,
        *,
        persona: Optional[Persona] = None,
        ask_guest_persona: bool = False,
        reference: Optional[str] = None,
        requester_name: Optional[str] = None,
        name: Optional[str] = None,
    ) -> CaptureLink:
        """Crea un enlace de un solo uso para que tu cliente escriba su CURP.

        Con ``persona`` (los datos de la reservación) la CURP se coteja contra
        ellos sin mostrárselos (``cotejo_reserva``); con
        ``ask_guest_persona=True`` el cliente también escribe su nombre y fecha
        de nacimiento (``cotejo``).

        Crearlo no cuesta; cada respuesta del cliente cuesta 1 token (hasta 3
        intentos) y solo una CURP válida que coincide llega a
        ``destination_id``.

        Lanza :class:`VerificarCurpError` (``DESTINATION_NOT_FOUND``,
        ``INVALID_PERSONA``, ``TOO_MANY_LIVE_LINKS``, …).
        """
        if not destination_id:
            raise VerificarCurpError("Falta `destination_id`.", "INVALID_INPUT")

        payload: dict = {"destinationId": destination_id}
        if persona is not None:
            payload["persona"] = persona
        if ask_guest_persona:
            payload["askGuestPersona"] = True
        if reference is not None:
            payload["reference"] = reference
        if requester_name is not None:
            payload["requesterName"] = requester_name
        if name is not None:
            payload["name"] = name

        body = self._request("POST", "/capture-links", json_body=payload)
        return CaptureLink(
            id=body["id"],
            url=body["url"],
            reference=body.get("reference"),
            ask_guest_persona=bool(body.get("askGuestPersona", False)),
            expires_at=body["expiresAt"],
        )

    # -- internals ---------------------------------------------------------

    def _request(self, method: str, path: str, *, json_body: Optional[dict] = None) -> Any:
        headers = {"X-API-Key": self.api_key, "User-Agent": USER_AGENT}
        data: Optional[bytes] = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)

        try:
            resp = self._opener(req, self.timeout)
            status = getattr(resp, "status", None) or resp.getcode()
            raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise VerificarCurpError.from_response(exc.code, _parse_json(exc.read())) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise VerificarCurpError(
                    f"La petición excedió el timeout de {self.timeout}s.", "TIMEOUT"
                ) from exc
            raise VerificarCurpError(str(exc.reason), "NETWORK_ERROR") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise VerificarCurpError(
                f"La petición excedió el timeout de {self.timeout}s.", "TIMEOUT"
            ) from exc

        body = _parse_json(raw)
        if status >= 400 or (isinstance(body, dict) and body.get("success") is False):
            raise VerificarCurpError.from_response(status, body)
        return body


def _parse_json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        return {}
