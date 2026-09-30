"""python examples/validar.py PEGJ850101HDFRRL04"""

import os
import sys

from verificar_curp import VerificarCurpClient

client = VerificarCurpClient(api_key=os.environ["CURP_API_KEY"])
curp = sys.argv[1] if len(sys.argv) > 1 else "PEGJ850101HDFRRL04"

result = client.validate(curp)
print("Válida" if result.data["valida"] else "No válida", result.data["razon"] or "", result.data["entidad"] or "")
print("Tokens restantes:", result.tokens_remaining)
