"""
POS Terminal Module
--------------------
Simulates the terminal side of a contactless transaction. Real EMV
contactless terminals exchange a sequence of APDU (Application Protocol
Data Unit) commands with the card over ISO 7816 / ISO 14443. We name our
steps after the real command sequence so the project accurately reflects
how contactless payments actually work, even though the wire format here
is simplified JSON instead of raw APDU bytes.

Real APDU flow (simplified):
1. SELECT           - terminal selects the payment application (e.g. Visa/MC AID)
2. GPO               (GET PROCESSING OPTIONS) - card responds with app info
3. READ RECORD      - terminal reads card data records
4. GENERATE AC      (Application Cryptogram) - card returns the ARQC used for
                      online authorization - this maps to our
                      `card.generate_cryptogram()` call
"""

import time
import requests


class POSTerminal:
    def __init__(self, terminal_id: str, processor_url: str = "http://localhost:5000"):
        self.terminal_id = terminal_id
        self.processor_url = processor_url

    def select_application(self):
        """Step 1: SELECT - terminal announces it wants to start a payment app session."""
        return {"step": "SELECT", "status": "ok", "terminal_id": self.terminal_id}

    def get_processing_options(self, card):
        """Step 2: GPO - terminal asks card what it supports (kept simple/simulated)."""
        return {"step": "GPO", "status": "ok", "supports": ["contactless_emv"]}

    def generate_ac(self, card, amount: float):
        """
        Step 3: GENERATE AC - the actual "tap." Card returns token + cryptogram.
        This is the only step that produces sensitive-ish data, and even that
        is a token + one-time cryptogram, never the real PAN.
        """
        return card.generate_cryptogram(terminal_id=self.terminal_id, amount=amount)

    def process_transaction(self, card, amount: float) -> dict:
        """
        Runs the full simulated tap sequence, then forwards the resulting
        token + cryptogram to the payment processor for authorization.
        This is the single entry point the rest of the app calls.
        """
        self.select_application()
        self.get_processing_options(card)
        tap_data = self.generate_ac(card, amount)

        payload = {
            "token": tap_data["token"],
            "cryptogram": tap_data["cryptogram"],
            "atc": tap_data["atc"],
            "terminal_id": tap_data["terminal_id"],
            "amount": tap_data["amount"],
            "timestamp": tap_data["timestamp"],
            "transaction_id": tap_data["transaction_id"],
            "tap_started_at": time.time(),  # used later for relay-attack timing checks
        }

        try:
            resp = requests.post(f"{self.processor_url}/api/authorize", json=payload, timeout=5)
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"status": "error", "reason": "processor_unreachable", "payload": payload}
