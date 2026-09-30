"""Errores del SDK de Verificar CURP."""

from __future__ import annotations

from typing import Any, Optional


class VerificarCurpError(Exception):
    """Error ante una respuesta no exitosa de la API, un fallo de red o una
    firma de webhook inválida. Inspecciona :attr:`code`.

    Códigos de la API: ``INVALID_REQUEST``, ``DESTINATION_NOT_FOUND``,
    ``MISSING_API_KEY``, ``INVALID_API_KEY``, ``INSUFFICIENT_TOKENS``,
    ``NOT_FOUND``, ``IDEMPOTENCY_KEY_REUSED``, ``INTERNAL_ERROR``.

    Códigos propios del SDK: ``NETWORK_ERROR``, ``TIMEOUT``, ``INVALID_INPUT``,
    ``INVALID_SIGNATURE``.

    https://verificarcurp.com/docs
    """

    def __init__(
        self,
        message: str,
        code: str,
        *,
        status: Optional[int] = None,
        block_reason: Optional[str] = None,
        response: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.block_reason = block_reason
        self.response = response

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.code}] {self.message}"

    @classmethod
    def from_response(cls, status: int, body: Any) -> "VerificarCurpError":
        """Construye el error a partir de una respuesta de la API."""
        b = body if isinstance(body, dict) else {}
        code = b.get("code") if isinstance(b.get("code"), str) else "INTERNAL_ERROR"
        message = (
            b.get("error")
            if isinstance(b.get("error"), str)
            else f"La API respondió con status {status}"
        )
        return cls(
            message,
            code,
            status=status,
            block_reason=b.get("block_reason") if isinstance(b.get("block_reason"), str) else None,
            response=body,
        )
