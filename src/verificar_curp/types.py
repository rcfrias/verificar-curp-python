"""Tipos de la API de Verificar CURP.

Los nombres de campo son los de la API y de https://verificarcurp.com/docs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, TypedDict, Union


class Persona(TypedDict, total=False):
    """Lo que ya sabes de la persona. Solo se compara lo que mandas.

    ``segundoApellido: None`` significa "no tiene segundo apellido" (y se
    compara); omitirlo significa "no comparar".
    """

    nombres: str
    primerApellido: str
    segundoApellido: Optional[str]
    fechaNacimiento: str  # AAAA-MM-DD
    sexo: str  # H o M
    entidad: str


class Reintentos(TypedDict, total=False):
    """Cambia, solo para esta petición, los reintentos automáticos."""

    activo: bool
    max: int
    espera_s: int


# Respuestas: diccionarios tal cual los devuelve la API.
CurpAnswer = Dict[str, Any]
"""``curp``, ``valida``, ``razon``, ``fechaNacimiento``, ``sexo``,
``claveEntidad``, ``entidad``, ``cotejo``, ``cotejoCampos``."""

Verificacion = Dict[str, Any]
"""Aceptada: ``aceptada=True``, ``job_id``, ``estado``, ``expires_at``.
Rechazada: ``aceptada=False``, ``codigo``, ``retry_after``."""

RegistryValues = Dict[str, str]
"""``estatus`` (ACTIVA, BAJA, RNE, NO_ENCONTRADA), ``curp``, ``nombres``, …"""


@dataclass(frozen=True)
class ValidateResult:
    data: CurpAnswer
    tokens_remaining: int
    #: Solo cuando pediste ``verificar``.
    verificacion: Optional[Verificacion] = None


@dataclass(frozen=True)
class VerificationStatusResult:
    verificacion: Dict[str, Any]
    #: El resultado del registro, entregado UNA sola vez y borrado en la misma
    #: operación. ``None`` si ya se entregó.
    valores: Optional[RegistryValues] = None


RawBody = Union[str, bytes, bytearray]

__all__ = [
    "Persona",
    "Reintentos",
    "CurpAnswer",
    "Verificacion",
    "RegistryValues",
    "ValidateResult",
    "VerificationStatusResult",
    "RawBody",
]
