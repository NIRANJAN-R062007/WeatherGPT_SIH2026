"""Local WhatsApp simulation (plan.md §8 Phase 5): no Meta app, no phone.

Sends one signed webhook POST through the real app (signature check, message
parsing, language choice, the real /ask pipeline) and prints the reply the bot
would have sent. Only the Graph API call is replaced. Every console line is
prefixed [SIMULATED]; nothing leaves this machine except what /ask itself
fetches (live weather and LLM keys if configured, fixtures otherwise).

    cd services/orchestrator
    .venv/bin/python whatsapp_simulate.py "Will it rain in Chennai today?"
    .venv/bin/python whatsapp_simulate.py "மழை பெய்யுமா சென்னை" --sender 919000000001
    .venv/bin/python whatsapp_simulate.py "2" "क्या आज चेन्नई में बारिश होगी?"
    .venv/bin/python whatsapp_simulate.py "weather in Puttur" "2"
    .venv/bin/python whatsapp_simulate.py "will it rain here today" "loc:13.08,80.27"

A message of the form loc:LAT,LON is sent as a shared location.
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import uuid

SECRET = "simulated-app-secret"
PHONE_NUMBER_ID = "0"


def _say(line: str) -> None:
    print(f"[SIMULATED] {line}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("texts", nargs="+",
                        help="messages to send, in order (loc:LAT,LON shares a location)")
    parser.add_argument("--sender", default="919999900000", help="fake sender number")
    args = parser.parse_args(argv)

    os.environ.update({
        "WHATSAPP_ENABLED": "1", "WHATSAPP_APP_SECRET": SECRET,
        "WHATSAPP_VERIFY_TOKEN": "simulated-verify", "WHATSAPP_ACCESS_TOKEN": "simulated-token",
        "WHATSAPP_PHONE_NUMBER_ID": PHONE_NUMBER_ID, "WHATSAPP_SENDER_RATE_PER_MIN": "0",
    })
    import main as orchestrator
    import whatsapp
    from fastapi.testclient import TestClient

    sent: list[tuple[str, str]] = []
    whatsapp.send_text = lambda to, body: sent.append((to, body)) or True

    client = TestClient(orchestrator.app)
    for text in args.texts:
        message = {"from": args.sender, "id": f"SIM-{uuid.uuid4().hex}"}
        if text.startswith("loc:"):
            lat, lon = (float(part) for part in text[4:].split(","))
            message.update(type="location", location={"latitude": lat, "longitude": lon})
        else:
            message.update(type="text", text={"body": text})
        payload = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": PHONE_NUMBER_ID}, "messages": [message]}}]}]}
        body = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        _say(f"-> {text}")
        resp = client.post("/whatsapp/webhook", content=body,
                           headers={"x-hub-signature-256": signature})
        if resp.status_code != 200:
            _say(f"webhook refused the message: HTTP {resp.status_code}")
            return 1
        while sent:
            _say(f"<- {sent.pop(0)[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
