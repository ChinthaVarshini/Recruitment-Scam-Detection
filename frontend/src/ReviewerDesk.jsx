import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "/api";

async function readResponse(response) {
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.detail || "Reviewer request failed.");
    error.status = response.status;
    throw error;
  }
  return data;
}

function ReviewerDesk({ visible, onClose }) {
  const [keyInput, setKeyInput] = useState("");
  const [adminKey, setAdminKey] = useState("");
  const [feedback, setFeedback] = useState([]);
  const [notes, setNotes] = useState({});
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  if (!visible) return null;

  const loadPending = async (key) => {
    setError("");
    setMessage("");
    setLoading(true);
    try {
      const data = await readResponse(await fetch(`${API_URL}/admin/feedback?review_status=PENDING`, {
        headers: { "X-Admin-Key": key },
      }));
      setAdminKey(key);
      setFeedback(data.feedback);
    } catch (requestError) {
      if (requestError.status === 401) {
        setAdminKey("");
        setFeedback([]);
      }
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const authenticate = (event) => {
    event.preventDefault();
    if (!keyInput.trim()) {
      setError("Enter the reviewer key to continue.");
      return;
    }
    loadPending(keyInput.trim());
  };

  const decide = async (item, decision) => {
    setError("");
    setMessage("");
    setBusyId(item.id);
    try {
      await readResponse(await fetch(`${API_URL}/admin/feedback/${item.id}/review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Key": adminKey,
        },
        body: JSON.stringify({ decision, review_note: notes[item.id] || "" }),
      }));
      await loadPending(adminKey);
      setMessage(`Review decision saved for ${item.title}.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyId(null);
    }
  };

  const signOut = () => {
    setAdminKey("");
    setKeyInput("");
    setFeedback([]);
    setNotes({});
    setMessage("");
    setError("");
  };

  return (
    <section className="reviewer-desk" aria-labelledby="reviewer-desk-title">
      <div className="reviewer-desk-heading">
        <div>
          <span className="analytics-kicker">AUTHORIZED REVIEW</span>
          <h3 id="reviewer-desk-title">Reviewer Desk</h3>
          <p>Verify each report independently. Pending user labels are not ground truth.</p>
        </div>
        <div className="reviewer-desk-tools">
          {adminKey && <button type="button" className="reviewer-text-button" onClick={signOut}>Sign out</button>}
          <button type="button" className="reviewer-text-button" onClick={onClose}>Close</button>
        </div>
      </div>

      {!adminKey && (
        <form className="reviewer-auth" onSubmit={authenticate}>
          <label htmlFor="reviewer-key">Server reviewer key</label>
          <input
            id="reviewer-key"
            type="password"
            autoComplete="current-password"
            value={keyInput}
            onChange={(event) => setKeyInput(event.target.value)}
            maxLength={500}
            required
          />
          <button type="submit" disabled={loading}>{loading ? "Checking..." : "Authenticate"}</button>
        </form>
      )}

      {adminKey && (
        <div className="reviewer-queue-heading">
          <strong>{feedback.length} pending reports</strong>
          <button type="button" className="reviewer-text-button" onClick={() => loadPending(adminKey)} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh queue"}
          </button>
        </div>
      )}

      {message && <p className="reviewer-success" role="status">{message}</p>}
      {error && <p className="reviewer-error" role="alert">{error}</p>}
      {adminKey && !loading && feedback.length === 0 && <p className="reviewer-empty">No pending feedback to review.</p>}

      <div className="reviewer-queue">
        {feedback.map((item) => (
          <article className="reviewer-item" key={item.id}>
            <div className="reviewer-item-heading">
              <div>
                <h4>{item.title}</h4>
                <span>Submitted {new Date(item.submitted_at).toLocaleString()}</span>
              </div>
              <span className="reviewer-pending-badge">Pending</span>
            </div>
            <dl className="reviewer-details">
              <div><dt>Model prediction</dt><dd>{item.model_prediction}</dd></div>
              <div><dt>Risk score</dt><dd>{item.final_risk_score == null ? "Unavailable" : `${item.final_risk_score}%`}</dd></div>
              <div><dt>Risk level</dt><dd>{item.risk_level}</dd></div>
              <div><dt>User label</dt><dd>{item.user_label}</dd></div>
            </dl>
            {item.comment && <p className="reviewer-note"><strong>User note:</strong> {item.comment}</p>}
            <label className="reviewer-note-input">
              Reviewer note (optional)
              <textarea
                value={notes[item.id] || ""}
                maxLength={1000}
                rows={2}
                onChange={(event) => setNotes((previous) => ({ ...previous, [item.id]: event.target.value }))}
                disabled={busyId === item.id}
              />
            </label>
            <div className="reviewer-decisions" aria-label={`Review decisions for ${item.title}`}>
              <button type="button" onClick={() => decide(item, "VERIFIED_FRAUDULENT")} disabled={busyId === item.id}>
                Verify fraudulent
              </button>
              <button type="button" onClick={() => decide(item, "VERIFIED_LEGITIMATE")} disabled={busyId === item.id}>
                Verify legitimate
              </button>
              <button type="button" className="reviewer-reject" onClick={() => decide(item, "REJECTED")} disabled={busyId === item.id}>
                Reject report
              </button>
            </div>
            {busyId === item.id && <p className="reviewer-loading" role="status">Saving review decision...</p>}
          </article>
        ))}
      </div>
    </section>
  );
}

export default ReviewerDesk;