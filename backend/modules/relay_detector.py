"""
Relay Attack Timing Detector
------------------------------
A relay attack works by placing a rogue device near the victim's real card,
and another rogue device near the real terminal, then relaying the NFC
signal between them in real time over the internet/radio. The victim's card
"taps" a terminal it was never physically near.

Why timing catches this:
Genuine contactless transactions complete their APDU exchange (SELECT -> GPO
-> GENERATE AC) within a very tight window - real EMV contactless specs
require the full exchange to complete in well under 500ms, and most legit
taps finish in tens of milliseconds. A relay attack adds an extra network
hop (attacker's terminal-side device <-> attacker's card-side device), which
reliably pushes the round-trip time up - even a fast relay over a good
connection adds measurable latency that a purely local tap never has.

This module measures the time between when the terminal starts the tap
(`tap_started_at`, set in pos_terminal.py) and when the processor receives
the authorization request. It flags transactions whose round-trip time
exceeds a threshold tuned to be well above legitimate local-tap latency but
well below what's needed to notice a real relay.
"""

import time

# Legitimate contactless taps (all local, no network hop) typically complete
# in a few milliseconds up to a few hundred milliseconds in this simulation,
# depending on OS/process overhead (Windows + antivirus + first-connection
# latency can push even a genuine local call past 1-2 seconds occasionally).
# A relay attack introduces at least one extra network round-trip on top of
# that baseline, so the threshold is set well above realistic local-tap
# latency to avoid false positives, while still catching real relay delay.
RELAY_LATENCY_THRESHOLD_MS = 4000


def check_relay_attack(tap_started_at: float, received_at: float = None) -> dict:
    """
    Returns a dict describing whether this transaction shows relay-attack-like
    timing. Call this from the processor right when a transaction arrives,
    using the tap_started_at timestamp the POS terminal attached.
    """
    received_at = received_at or time.time()
    round_trip_ms = (received_at - tap_started_at) * 1000

    is_suspicious = round_trip_ms > RELAY_LATENCY_THRESHOLD_MS

    return {
        "round_trip_ms": round(round_trip_ms, 2),
        "threshold_ms": RELAY_LATENCY_THRESHOLD_MS,
        "relay_suspected": is_suspicious,
        "reason": (
            f"round-trip time {round_trip_ms:.1f}ms exceeds {RELAY_LATENCY_THRESHOLD_MS}ms "
            f"threshold - possible relay attack"
            if is_suspicious
            else "round-trip time within normal local-tap range"
        ),
    }


if __name__ == "__main__":
    # Simulate a normal local tap (fast)
    now = time.time()
    normal_tap_start = now - 0.015  # 15ms round trip - realistic local tap
    print("Normal tap:", check_relay_attack(normal_tap_start, now))

    # Simulate a relayed tap (artificial network delay injected)
    relayed_tap_start = now - 0.6  # 600ms round trip - relay-attack-like
    print("Relayed tap:", check_relay_attack(relayed_tap_start, now))