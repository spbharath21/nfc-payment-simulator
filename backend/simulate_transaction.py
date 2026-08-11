"""
End-to-end simulation script.
Run the Flask app first (python app.py), then run this in a separate terminal.

This mimics the full real-world flow:
  1. Card gets provisioned (issuance)
  2. Card's token gets registered in the processor's vault (this normally
     happens once, at card issuance time, via the card network)
  3. Card taps a POS terminal -> generates cryptogram -> POS sends to processor
  4. Processor validates + approves/declines
"""

import requests
from modules.card_emulator import provision_card
from modules.pos_terminal import POSTerminal

PROCESSOR_URL = "http://localhost:5000"


def mask_pan(pan: str) -> str:
    return pan[:6] + "*" * (len(pan) - 10) + pan[-4:]


def main():
    # 1. Provision a virtual card
    card = provision_card(pan="4111111111111111", expiry="12/28", cardholder="S P Bharath")
    token = card._derive_token()

    # 2. Register the card's token in the processor's vault (one-time step)
    resp = requests.post(f"{PROCESSOR_URL}/api/vault/register", json={
        "token": token,
        "cardholder": card.cardholder,
        "masked_pan": mask_pan(card.pan),
        "balance": 5000.0,
    })
    print("Vault registration:", resp.json())

    # 3. Simulate three taps at a POS terminal
    terminal = POSTerminal(terminal_id="POS-BLR-001", processor_url=PROCESSOR_URL)

    for amount in [250.00, 1200.50, 999999.00]:  # last one should decline (insufficient funds)
        result = terminal.process_transaction(card, amount)
        print(f"\nTap for ₹{amount} -> {result['status'].upper()} ({result.get('reason')})")
        print(result)


if __name__ == "__main__":
    main()
