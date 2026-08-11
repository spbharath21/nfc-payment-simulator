"""
Fraud Detection Engine
------------------------
Scores each transaction against a small set of real-world fraud signals and
returns a risk score + human-readable reasoning. Same "anomaly scoring"
pattern used in phishing/log-based detection - just applied to payment
transactions instead of URLs/log lines.

Signals implemented:
1. Velocity      - too many taps from the same token in a short window
                    (classic card-testing / stolen-card-spree pattern)
2. Amount anomaly - transaction amount is a large multiple of the
                    account's historical average (sudden spend spike)
3. Geo jump       - two taps from the same token at "impossible" distance
                    apart within a short time window (physically can't be
                    the same card/person)

Each signal contributes a weighted score. Score >= BLOCK_THRESHOLD -> flagged
for review / declined. This mirrors how real card-network fraud engines
(e.g. Visa Advanced Authorization) combine multiple weak signals into one
decision rather than relying on a single rule.
"""

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field


# --- Tunable thresholds -----------------------------------------------------
VELOCITY_WINDOW_SECONDS = 60      # look-back window for velocity check
VELOCITY_MAX_TAPS = 3             # more than this many taps in the window = suspicious
AMOUNT_ANOMALY_MULTIPLIER = 5.0   # amount > 5x historical average = suspicious
GEO_IMPOSSIBLE_SPEED_KMH = 900    # faster than a commercial flight = impossible
BLOCK_THRESHOLD = 70              # score out of 100 -> flag/decline


@dataclass
class TokenHistory:
    """Rolling history kept per token (per card), used to compute the signals above."""
    amounts: list = field(default_factory=list)
    taps: list = field(default_factory=list)  # list of (timestamp, lat, lon)

    def avg_amount(self) -> float:
        return sum(self.amounts) / len(self.amounts) if self.amounts else 0.0


class FraudDetectionEngine:
    def __init__(self):
        self.history: dict[str, TokenHistory] = defaultdict(TokenHistory)

    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2) -> float:
        """Great-circle distance between two lat/lon points, in km."""
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return 2 * R * math.asin(math.sqrt(a))

    def _velocity_score(self, token: str, now: float) -> tuple[int, str | None]:
        recent = [t for t in self.history[token].taps if now - t[0] <= VELOCITY_WINDOW_SECONDS]
        if len(recent) > VELOCITY_MAX_TAPS:
            return 40, f"velocity: {len(recent)} taps in {VELOCITY_WINDOW_SECONDS}s (limit {VELOCITY_MAX_TAPS})"
        return 0, None

    def _amount_score(self, token: str, amount: float) -> tuple[int, str | None]:
        avg = self.history[token].avg_amount()
        if avg > 0 and amount > avg * AMOUNT_ANOMALY_MULTIPLIER:
            return 35, f"amount anomaly: ₹{amount:.2f} is {amount / avg:.1f}x the account average (₹{avg:.2f})"
        return 0, None

    def _geo_score(self, token: str, now: float, lat: float, lon: float) -> tuple[int, str | None]:
        taps = self.history[token].taps
        if not taps:
            return 0, None
        last_ts, last_lat, last_lon = taps[-1]
        dt_hours = max((now - last_ts) / 3600.0, 1e-6)
        distance = self._haversine_km(last_lat, last_lon, lat, lon)
        implied_speed = distance / dt_hours
        if implied_speed > GEO_IMPOSSIBLE_SPEED_KMH and distance > 50:
            return 45, f"geo jump: {distance:.0f}km in {dt_hours*60:.1f}min (implied speed {implied_speed:.0f} km/h)"
        return 0, None

    def score_transaction(self, token: str, amount: float, lat: float = 12.9716, lon: float = 77.5946,
                           now: float | None = None) -> dict:
        """
        Main entry point. Call this BEFORE finalizing authorization.
        Returns a dict with the total risk score, individual signal reasons,
        and a decision recommendation.
        Default lat/lon is Bengaluru so single-location demos work out of the box.
        """
        now = now or time.time()

        v_score, v_reason = self._velocity_score(token, now)
        a_score, a_reason = self._amount_score(token, amount)
        g_score, g_reason = self._geo_score(token, now, lat, lon)

        total_score = v_score + a_score + g_score
        reasons = [r for r in (v_reason, a_reason, g_reason) if r]

        decision = "flagged" if total_score >= BLOCK_THRESHOLD else "clear"

        # record this tap into history AFTER scoring (so it doesn't compare against itself)
        self.history[token].amounts.append(amount)
        self.history[token].taps.append((now, lat, lon))

        return {
            "risk_score": total_score,
            "decision": decision,
            "reasons": reasons if reasons else ["no anomalies detected"],
        }


if __name__ == "__main__":
    # quick manual smoke test
    engine = FraudDetectionEngine()
    tok = "tok_demo123"

    # normal small transactions build up a baseline average
    for amt in [200, 250, 300]:
        print(engine.score_transaction(tok, amt))

    # sudden huge transaction relative to history -> should flag amount anomaly
    print(engine.score_transaction(tok, 5000))

    # rapid-fire taps -> should flag velocity
    for _ in range(4):
        print(engine.score_transaction(tok, 100))

    # impossible geo jump: Bengaluru -> New York within a minute
    print(engine.score_transaction(tok, 150, lat=12.9716, lon=77.5946))
    print(engine.score_transaction(tok, 150, lat=40.7128, lon=-74.0060))
