"""SDK oficial de Verificar CURP: valida, coteja y verifica CURPs en RENAPO.

https://verificarcurp.com/docs
"""

from .client import VerificarCurpClient
from .errors import VerificarCurpError
from .types import CaptureLink, Persona, Reintentos, ValidateResult, VerificationStatusResult
from .webhooks import (
    IDEMPOTENCY_KEY_HEADER,
    SIGNATURE_HEADER,
    SIGNATURE_TIMESTAMP_HEADER,
    parse_webhook,
    verify_webhook_signature,
)

__all__ = [
    "VerificarCurpClient",
    "VerificarCurpError",
    "CaptureLink",
    "Persona",
    "Reintentos",
    "ValidateResult",
    "VerificationStatusResult",
    "verify_webhook_signature",
    "parse_webhook",
    "SIGNATURE_HEADER",
    "SIGNATURE_TIMESTAMP_HEADER",
    "IDEMPOTENCY_KEY_HEADER",
]

__version__ = "1.1.0"
