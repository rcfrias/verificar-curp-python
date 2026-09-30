# verificar-curp

SDK oficial de [Verificar CURP](https://verificarcurp.com) para Python.

- **Valida** la estructura de una CURP (entidad, fecha, dígito verificador) y te dice qué está mal.
- **Coteja** la CURP con los datos que ya tienes de la persona.
- **Verifica** la CURP en el registro RENAPO; el resultado llega a tu webhook, correo o chat.
- **Verifica la firma** de los webhooks que te enviamos.

Sin dependencias. Python 3.9+.

```bash
pip install verificar-curp
```

## Uso

```python
import os
from verificar_curp import VerificarCurpClient

client = VerificarCurpClient(api_key=os.environ["CURP_API_KEY"])

result = client.validate(
    "PEGJ850101HDFRRL04",
    persona={"nombres": "Julio", "fechaNacimiento": "1985-01-01", "sexo": "H"},
)

result.data["valida"]        # True
result.data["entidad"]       # 'Ciudad de México'
result.data["cotejo"]        # 'coincide' | 'no_coincide' | 'indeterminado'
result.data["cotejoCampos"]  # {'nombres': 'coincide', ...}
result.tokens_remaining
```

Una CURP mal formada no es un error: `data["valida"]` es `False` y el motivo va en `data["razon"]`
(por ejemplo `{"kind": "check-digit", "expected": "4", "actual": "9"}`).

En `persona`, `"segundoApellido": None` significa "no tiene segundo apellido" y se compara; si omites
la clave, no se compara.

## Verificar en RENAPO

```python
result = client.validate(
    "PEGJ850101HDFRRL04",
    verificar=True,
    destination_id="dst_...",        # panel → Destinos
    idempotency_key="cliente-123",   # opcional; nunca pongas la CURP aquí
)

v = result.verificacion
if v and v["aceptada"]:
    print("En curso:", v["job_id"])
elif v:
    print("No se pudo iniciar:", v["codigo"], "reintenta en", v["retry_after"], "s")
```

El resultado del registro (`estatus`: `ACTIVA`, `BAJA`, `RNE` o `NO_ENCONTRADA`) llega a tu destino,
normalmente en segundos. También puedes consultar el estado, sin costo:

```python
status = client.get_verification(job_id)
status.verificacion["estado"]
status.valores  # dict o None
```

`valores` llega **una sola vez** y se borra en la misma operación. Si tu destino ya lo recibió, aquí
solo verás el estado; es la forma de recuperarlo cuando la entrega a tu destino falló.

## Recibir el webhook

Verifica la firma con el cuerpo **crudo**, antes de interpretarlo:

```python
from flask import Flask, request
from verificar_curp import VerificarCurpError, parse_webhook

app = Flask(__name__)

@app.post("/webhooks/curp")
def curp_webhook():
    try:
        event = parse_webhook(
            os.environ["CURP_WEBHOOK_SECRET"],  # whsec_…
            request.get_data(),
            request.headers.get("X-Signature"),
            request.headers.get("X-Signature-Timestamp"),
        )
    except VerificarCurpError:
        return "", 400

    if event["event"] == "curp.verification.completed":
        print(event["idempotencyKey"], event["data"]["estatus"])
    return "", 200
```

`verify_webhook_signature()` hace lo mismo y devuelve `True`/`False`. Por defecto rechaza firmas con
más de 300 s de antigüedad (`tolerance_seconds`). Eventos: `curp.verification.completed`, `.failed`,
`.retrying` y `.manual_review`.

## Saldo

```python
tokens = client.get_balance()
```

## Errores

Todo fallo lanza `VerificarCurpError`, con `code`, `status`, `block_reason` y el cuerpo crudo en
`response`:

```python
from verificar_curp import VerificarCurpError

try:
    client.validate(curp)
except VerificarCurpError as err:
    if err.code == "INSUFFICIENT_TOKENS":
        ...  # recarga tokens en https://verificarcurp.com
```

| code | status | cuándo |
| --- | --- | --- |
| `INVALID_REQUEST` | 400 | Cuerpo inválido |
| `DESTINATION_NOT_FOUND` | 400 | El destino no existe o no es tuyo (no se cobra) |
| `MISSING_API_KEY` / `INVALID_API_KEY` | 401 | API key ausente o incorrecta |
| `INSUFFICIENT_TOKENS` | 402 | Sin saldo |
| `NOT_FOUND` | 404 | La verificación no es de tu cuenta |
| `IDEMPOTENCY_KEY_REUSED` | 409 | Misma `idempotency_key` con otra CURP |
| `INTERNAL_ERROR` | 500 | Error del servidor |
| `NETWORK_ERROR` / `TIMEOUT` | — | Del SDK |
| `INVALID_INPUT` / `INVALID_SIGNATURE` | — | Del SDK |

## Enlaces

- Documentación: https://verificarcurp.com/docs
- OpenAPI: https://verificarcurp.com/api/openapi.yaml
- JavaScript / TypeScript: https://www.npmjs.com/package/verificar-curp

MIT
