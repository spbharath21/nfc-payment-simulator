"""
Fraud-triggering test: registers a card, then fires rapid-fire taps to
trigger the velocity signal, confirming the processor declines with
reason 'fraud_flagged' once the fraud engine's threshold is crossed.
"""

import requests
from modules.card_emulator import provision_card
from modules.pos_terminal import POSTerminal

PROCESSOR_URL = "http://localhost:5000"


def mask_pan(pan: str) -> str:
    return pan[:6] + "*" * (len(pan) - 10) + pan[-4:]


def main():
    card = provision_card(pan="4222222222222222", expiry="10/29", cardholder="Test Fraud User")
    token = card._derive_token()

    requests.post(f"{PROCESSOR_URL}/api/vault/register", json={
        "token": token,
        "cardholder": card.cardholder,
        "masked_pan": mask_pan(card.pan),
        "balance": 50000.0,
    })

    terminal = POSTerminal(terminal_id="POS-BLR-002", processor_url=PROCESSOR_URL)

    print("Phase A: building a normal spending baseline (small amounts)...\n")
    for amt in [150, 180, 200]:
        result = terminal.process_transaction(card, amount=amt)
        print(f"₹{amt}: {result['status'].upper()} | fraud={result.get('fraud')}")

    print("\nPhase B: rapid-fire taps + a large amount spike -> should combine to FLAGGED...\n")
    for i in range(5):
        amt = 100.0 if i < 4 else 3000.0  # last tap is both rapid AND a big spike
        result = terminal.process_transaction(card, amount=amt)
        print(f"Tap {i+1} (₹{amt}): {result['status'].upper()} | reason={result.get('reason')} | "
              f"fraud={result.get('fraud')}")


if __name__ == "__main__":
    main()
