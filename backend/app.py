"""
Payment Processor / Token Vault
---------------------------------
This is the "bank/network side" of the simulation - equivalent to what
Visa Token Service, or Amazon Pay's backend, does: receive a token +
cryptogram (never the real PAN), validate it, and approve/decline.

Endpoints:
  POST /api/authorize   - main transaction authorization endpoint
  GET  /api/transactions - list recent transactions (for the dashboard)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import uuid

from modules.fraud_detection import FraudDetectionEngine
from modules.relay_detector import check_relay_attack

app = Flask(__name__)
CORS(app)  # allows the React dashboard (running on a different port) to fetch this API

# --- In-memory "token vault" and transaction log (swap for MongoDB later) ---
# token_vault maps token -> { real pan (masked), cardholder, balance, expiry }
token_vault = {}
transactions = []
fraud_engine = FraudDetectionEngine()


def register_card_token(token: str, cardholder: str, masked_pan: str, balance: float = 5000.0):
    """Called once at provisioning time - the vault only ever stores the token,
    never the real PAN in plaintext (here we store a masked version for demo
    purposes, e.g. '411111******1111')."""
    token_vault[token] = {
        "cardholder": cardholder,
        "masked_pan": masked_pan,
        "balance": balance,
    }


@app.route("/api/authorize", methods=["POST"])
def authorize():
    data = request.get_json()

    token = data.get("token")
    amount = data.get("amount")
    terminal_id = data.get("terminal_id")
    transaction_id = data.get("transaction_id", str(uuid.uuid4()))
    lat = data.get("lat", 12.9716)  # defaults to Bengaluru for single-location demos
    lon = data.get("lon", 77.5946)

    record = {
        "transaction_id": transaction_id,
        "token": token,
        "terminal_id": terminal_id,
        "amount": amount,
        "timestamp": datetime.utcnow().isoformat(),
        "atc": data.get("atc"),
        "tap_started_at": data.get("tap_started_at"),
        "status": "pending",
        "reason": None,
        "fraud": None,
        "relay_check": None,
    }

    # 1. Token must exist in vault
    if token not in token_vault:
        record["status"] = "declined"
        record["reason"] = "unknown_token"
        transactions.append(record)
        return jsonify(record), 200

    account = token_vault[token]

    # 2. Relay-attack timing check - runs before fraud/balance checks since a
    #    relayed transaction is fraudulent by definition regardless of amount
    tap_started_at = data.get("tap_started_at")
    if tap_started_at:
        relay_result = check_relay_attack(tap_started_at)
        record["relay_check"] = relay_result
        if relay_result["relay_suspected"]:
            record["status"] = "declined"
            record["reason"] = "relay_attack_suspected"
            transactions.append(record)
            return jsonify(record), 200

    # 3. Run fraud scoring BEFORE deciding on the balance check, so a flagged
    #    transaction is declined even if funds are available (mirrors how
    #    real issuers hold/decline suspicious transactions regardless of balance)
    fraud_result = fraud_engine.score_transaction(token=token, amount=amount, lat=lat, lon=lon)
    record["fraud"] = fraud_result

    if fraud_result["decision"] == "flagged":
        record["status"] = "declined"
        record["reason"] = "fraud_flagged"
        transactions.append(record)
        return jsonify(record), 200

    # 4. Basic balance check
    if amount is None or amount <= 0:
        record["status"] = "declined"
        record["reason"] = "invalid_amount"
    elif amount > account["balance"]:
        record["status"] = "declined"
        record["reason"] = "insufficient_funds"
    else:
        account["balance"] -= amount
        record["status"] = "approved"
        record["reason"] = "ok"
        record["remaining_balance"] = account["balance"]

    transactions.append(record)
    return jsonify(record), 200


@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    return jsonify(list(reversed(transactions))[:100])


@app.route("/api/vault/register", methods=["POST"])
def register():
    """Helper endpoint to provision a token into the vault (demo/testing use)."""
    data = request.get_json()
    register_card_token(
        token=data["token"],
        cardholder=data["cardholder"],
        masked_pan=data["masked_pan"],
        balance=data.get("balance", 5000.0),
    )
    return jsonify({"status": "registered", "token": data["token"]})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
