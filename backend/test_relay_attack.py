"""
Relay-attack test: simulates a normal tap (should approve) followed by a
"relayed" tap where we artificially delay the tap_started_at timestamp to
mimic the extra network hop a real relay attack introduces, confirming the
processor declines it with reason 'relay_attack_suspected'.
"""

import time
import requests
from modules.card_emulator import provision_card
from modules.pos_terminal import POSTerminal

PROCESSOR_URL = "http://localhost:5000"


def mask_pan(pan: str) -> str:
    return pan[:6] + "*" * (len(pan) - 10) + pan[-4:]


def main():
    card = provision_card(pan="4333333333333333", expiry="09/28", cardholder="Relay Test User")
    token = card._derive_token()

    requests.post(f"{PROCESSOR_URL}/api/vault/register", json={
        "token": token,
        "cardholder": card.cardholder,
        "masked_pan": mask_pan(card.pan),
        "balance": 10000.0,
    })

    terminal = POSTerminal(terminal_id="POS-BLR-003", processor_url=PROCESSOR_URL)

    print("Tap 1: normal local tap (should APPROVE)...\n")
    result = terminal.process_transaction(card, amount=300.0)
    print(f"Result: {result['status'].upper()} | reason={result.get('reason')} | "
          f"relay_check={result.get('relay_check')}\n")

    print("Tap 2: simulating a relayed tap (artificial 5s network delay)...\n")
    # Manually build the tap the way POSTerminal does, but inject delay into
    # tap_started_at to mimic what a real relay's extra hop would look like.
    tap_data = card.generate_cryptogram(terminal_id=terminal.terminal_id, amount=300.0)
    payload = {
        "token": tap_data["token"],
        "cryptogram": tap_data["cryptogram"],
        "atc": tap_data["atc"],
        "terminal_id": tap_data["terminal_id"],
        "amount": tap_data["amount"],
        "timestamp": tap_data["timestamp"],
        "transaction_id": tap_data["transaction_id"],
        "tap_started_at": time.time() - 5.0,  # backdate by 5s to simulate relay latency
    }
    resp = requests.post(f"{PROCESSOR_URL}/api/authorize", json=payload, timeout=5)
    result = resp.json()
    print(f"Result: {result['status'].upper()} | reason={result.get('reason')} | "
          f"relay_check={result.get('relay_check')}")


if __name__ == "__main__":
    main()