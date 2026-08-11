import { useEffect, useState, useRef } from "react";
import "./App.css";

const PROCESSOR_URL = "http://localhost:5000";
const POLL_INTERVAL_MS = 2000;

function StatusBadge({ status }) {
  const styles = {
    approved: { background: "#0f5132", color: "#d1e7dd", label: "APPROVED" },
    declined: { background: "#842029", color: "#f8d7da", label: "DECLINED" },
    pending: { background: "#664d03", color: "#fff3cd", label: "PENDING" },
  };
  const s = styles[status] || styles.pending;
  return (
    <span
      style={{
        background: s.background,
        color: s.color,
        padding: "2px 10px",
        borderRadius: "12px",
        fontSize: "0.75rem",
        fontWeight: 600,
        letterSpacing: "0.03em",
      }}
    >
      {s.label}
    </span>
  );
}

function FraudBadge({ fraud }) {
  if (!fraud) return <span style={{ color: "#6c757d" }}>—</span>;
  const flagged = fraud.decision === "flagged";
  return (
    <span
      title={fraud.reasons?.join(" | ")}
      style={{
        color: flagged ? "#ff8080" : "#6cbf6c",
        fontWeight: flagged ? 700 : 400,
        cursor: "help",
      }}
    >
      {flagged ? "⚠ " : "✓ "}
      {fraud.risk_score}/100
    </span>
  );
}

function RelayBadge({ relay }) {
  if (!relay) return <span style={{ color: "#6c757d" }}>—</span>;
  const suspected = relay.relay_suspected;
  return (
    <span
      title={relay.reason}
      style={{
        color: suspected ? "#ff8080" : "#6cbf6c",
        fontWeight: suspected ? 700 : 400,
        cursor: "help",
      }}
    >
      {suspected ? "⚠ " : "✓ "}
      {relay.round_trip_ms}ms
    </span>
  );
}

function App() {
  const [transactions, setTransactions] = useState([]);
  const [connectionError, setConnectionError] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const pollRef = useRef(null);

  const fetchTransactions = async () => {
    try {
      const res = await fetch(`${PROCESSOR_URL}/api/transactions`);
      if (!res.ok) throw new Error("bad response");
      const data = await res.json();
      setTransactions(data);
      setConnectionError(false);
      setLastUpdated(new Date());
    } catch (err) {
      setConnectionError(true);
    }
  };

  useEffect(() => {
    fetchTransactions();
    pollRef.current = setInterval(fetchTransactions, POLL_INTERVAL_MS);
    return () => clearInterval(pollRef.current);
  }, []);

  const totalCount = transactions.length;
  const approvedCount = transactions.filter((t) => t.status === "approved").length;
  const declinedCount = transactions.filter((t) => t.status === "declined").length;
  const flaggedCount = transactions.filter((t) => t.fraud?.decision === "flagged").length;

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div>
          <h1>NFC Payment Simulator</h1>
          <p className="subtitle">Live transaction feed — tokenized, fraud-scored authorization</p>
        </div>
        <div className="status-pill">
          {connectionError ? (
            <span style={{ color: "#ff8080" }}>● Processor unreachable — is app.py running?</span>
          ) : (
            <span style={{ color: "#6cbf6c" }}>
              ● Live {lastUpdated ? `— updated ${lastUpdated.toLocaleTimeString()}` : ""}
            </span>
          )}
        </div>
      </header>

      <section className="stat-cards">
        <div className="stat-card">
          <div className="stat-value">{totalCount}</div>
          <div className="stat-label">Total Transactions</div>
        </div>
        <div className="stat-card stat-approved">
          <div className="stat-value">{approvedCount}</div>
          <div className="stat-label">Approved</div>
        </div>
        <div className="stat-card stat-declined">
          <div className="stat-value">{declinedCount}</div>
          <div className="stat-label">Declined</div>
        </div>
        <div className="stat-card stat-flagged">
          <div className="stat-value">{flaggedCount}</div>
          <div className="stat-label">Fraud Flagged</div>
        </div>
      </section>

      <section className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Token</th>
              <th>Terminal</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Reason</th>
              <th>Fraud Score</th>
              <th>Relay Check</th>
            </tr>
          </thead>
          <tbody>
            {transactions.length === 0 && (
              <tr>
                <td colSpan={8} className="empty-row">
                  No transactions yet — run simulate_transaction.py or test_fraud_trigger.py
                </td>
              </tr>
            )}
            {transactions.map((t) => (
              <tr key={t.transaction_id}>
                <td>{new Date(t.timestamp).toLocaleTimeString()}</td>
                <td className="mono">{t.token?.slice(0, 16)}…</td>
                <td>{t.terminal_id}</td>
                <td>₹{Number(t.amount).toFixed(2)}</td>
                <td>
                  <StatusBadge status={t.status} />
                </td>
                <td className="reason-cell">{t.reason}</td>
                <td>
                  <FraudBadge fraud={t.fraud} />
                </td>
                <td>
                  <RelayBadge relay={t.relay_check} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

export default App;
