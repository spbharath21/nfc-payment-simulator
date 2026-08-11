"""
Card Emulator Module
---------------------
Simulates a contactless card (or phone in HCE mode). Never exposes the real
PAN (Primary Account Number) over the "air interface" — instead generates a
dynamic cryptogram per transaction, mirroring how real EMV contactless cards
and HCE-based wallets (Apple Pay / Google Pay / Amazon Pay) work.

Real-world parallel:
- PAN + expiry -> stored securely on the card / secure element
- Each tap -> card increments an Application Transaction Counter (ATC) and
  derives a fresh cryptogram (ARQC) using a per-card key + the ATC + terminal
  data. The cryptogram changes every single tap, so intercepting one is
  useless for the next transaction (this is what defeats basic card-skimming
  replay attacks).

Here we use HMAC-SHA256 as a stand-in for the real EMV MAC algorithms
(3DES/AES-based session key derivation), which is out of scope to
reimplement but conceptually equivalent for demo purposes.
"""

import hmac
import hashlib
import os
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class VirtualCard:
    """Represents a provisioned contactless card / HCE wallet entry."""

    pan: str  # Real card number - NEVER transmitted directly
    expiry: str  # MM/YY
    cardholder: str
    card_key: bytes = field(default_factory=lambda: os.urandom(32))  # per-card secret
    atc: int = 0  # Application Transaction Counter, increments every tap

    def _derive_token(self) -> str:
        """
        Derive a stable-per-card but non-reversible token to stand in for the
        PAN in downstream systems (this is what a tokenization service like
        Visa Token Service / Amazon Pay's vault stores instead of the PAN).
        """
        digest = hmac.new(self.card_key, self.pan.encode(), hashlib.sha256).hexdigest()
        return f"tok_{digest[:24]}"

    def generate_cryptogram(self, terminal_id: str, amount: float) -> dict:
        """
        Simulate a single NFC "tap": increment ATC, derive a fresh cryptogram
        bound to (card_key, ATC, terminal_id, amount, timestamp). Changing
        any of these changes the cryptogram entirely, so a captured
        cryptogram cannot be replayed for a different amount/terminal/time.
        """
        self.atc += 1
        timestamp = time.time()

        message = f"{self.atc}|{terminal_id}|{amount}|{timestamp}".encode()
        cryptogram = hmac.new(self.card_key, message, hashlib.sha256).hexdigest()

        return {
            "token": self._derive_token(),
            "cryptogram": cryptogram,
            "atc": self.atc,
            "terminal_id": terminal_id,
            "amount": amount,
            "timestamp": timestamp,
            "transaction_id": str(uuid.uuid4()),
        }


def provision_card(pan: str, expiry: str, cardholder: str) -> VirtualCard:
    """Factory function - simulates the card issuance / provisioning step."""
    return VirtualCard(pan=pan, expiry=expiry, cardholder=cardholder)


if __name__ == "__main__":
    # quick manual smoke test
    card = provision_card("4111111111111111", "12/28", "S P Bharath")
    tap1 = card.generate_cryptogram(terminal_id="POS-001", amount=250.00)
    tap2 = card.generate_cryptogram(terminal_id="POS-001", amount=250.00)
    print("Tap 1:", tap1)
    print("Tap 2:", tap2)
    print("Cryptograms differ even for identical amount/terminal:",
          tap1["cryptogram"] != tap2["cryptogram"])
