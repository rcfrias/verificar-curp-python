"""pip install flask && CURP_WEBHOOK_SECRET=whsec_... python examples/webhook_flask.py"""

import os

from flask import Flask, request

from verificar_curp import VerificarCurpError, parse_webhook

app = Flask(__name__)


@app.post("/webhooks/curp")
def curp_webhook():
    try:
        event = parse_webhook(
            os.environ["CURP_WEBHOOK_SECRET"],
            request.get_data(),
            request.headers.get("X-Signature"),
            request.headers.get("X-Signature-Timestamp"),
        )
    except VerificarCurpError as err:
        print(err)
        return "", 400
    print(event["event"], event["idempotencyKey"], event["data"])
    return "", 200


if __name__ == "__main__":
    app.run(port=3000)
