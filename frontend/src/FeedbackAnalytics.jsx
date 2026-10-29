import { useEffect, useState } from "react";
import { API_URL } from "./api.js";
import { readJsonResponse } from "./http.js";

function FeedbackAnalytics() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [displayCleared, setDisplayCleared] = useState(false);

  useEffect(() => {
    let active = true;

    const loadAnalytics = async () => {
      setLoading(true);
      setError("");
      try {
        const response = await fetch(`${API_URL}/feedback/analytics`);
        const data = await readJsonResponse(
          response,
          "Could not load feedback analytics.",
        );
        if (active) setAnalytics(data);
      } catch (requestError) {
        if (active) setError(requestError.message);
      } finally {
        if (active) setLoading(false);
      }
    };

    loadAnalytics();
    return () => {
      active = false;
    };
  }, [reloadKey]);

  const retry = () => setReloadKey((key) => key + 1);
  const evaluation = analytics?.evaluation;
  const labels = analytics?.user_submitted_label_counts;
  const verifiedLabels = analytics?.verified_label_counts;

  return (
    <section className="feedback-analytics" aria-labelledby="feedback-analytics-title" aria-busy={loading}>
      <div className="feedback-analytics-heading">
        <div>
          <span className="analytics-kicker">QUALITY SIGNALS</span>
          <h3 id="feedback-analytics-title">Feedback analytics</h3>
          <p>User-submitted labels are suggestions. Only independently reviewed labels are used for feedback-based evaluation.</p>
        </div>
        <div className="analytics-actions">
          <button
            type="button"
            className="analytics-refresh"
            onClick={() => {
              setDisplayCleared(false);
              retry();
            }}
            disabled={loading}
          >
            {loading ? "Loading..." : "Refresh"}
          </button>
          <button
            type="button"
            className="analytics-clear"
            onClick={() => setDisplayCleared((cleared) => !cleared)}
            disabled={loading || (!analytics?.total_submissions && !displayCleared)}
            aria-label={displayCleared ? "Show feedback analytics" : "Clear feedback analytics display"}
          >
            {displayCleared ? "Show data" : "Clear"}
          </button>
        </div>
      </div>

      {loading && <p className="analytics-status" role="status">Loading saved feedback data...</p>}
      {!loading && error && (
        <div className="analytics-error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={retry}>Try again</button>
        </div>
      )}

      {!loading && !error && analytics && displayCleared && (
        <p className="analytics-cleared" role="status">
          Analytics hidden from this view. Saved feedback remains in the database; use Show data or Refresh to display it again.
        </p>
      )}

      {!loading && !error && analytics && !displayCleared && (
        <>
          <div className="feedback-metrics">
            <div><span>Total reports</span><strong>{analytics.total_submissions}</strong></div>
            <div><span>User-reported fraudulent</span><strong>{labels.FRAUDULENT}</strong></div>
            <div><span>User-reported legitimate</span><strong>{labels.LEGITIMATE}</strong></div>
            <div><span>Awaiting review</span><strong>{analytics.pending_count}</strong></div>
            <div><span>Verified fraudulent</span><strong>{verifiedLabels.FRAUDULENT}</strong></div>
            <div><span>Verified legitimate</span><strong>{verifiedLabels.LEGITIMATE}</strong></div>
            <div><span>Rejected as unverified</span><strong>{analytics.rejected_count}</strong></div>
          </div>

          {analytics.total_submissions === 0 ? (
            <p className="analytics-empty">No feedback has been submitted yet. Feedback appears here after it is saved with an assessment.</p>
          ) : (
            <p className="analytics-disclaimer">User-reported counts are opinions, not confirmed outcomes. Only an authorized reviewer can verify a label; rejected reports are excluded from ground truth and evaluation.</p>
          )}

          {analytics.trends.length > 1 && (
            <div className="feedback-trends">
              <h4>Submissions over time</h4>
              <div className="feedback-trend-list" role="list" aria-label="Daily feedback submissions">
                {analytics.trends.map((item) => (
                  <div className="feedback-trend" key={item.day} role="listitem">
                    <span>{new Date(`${item.day}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
                    <div className="feedback-trend-track" aria-hidden="true">
                      <div style={{ width: `${Math.max(4, item.count / Math.max(...analytics.trends.map((trend) => trend.count)) * 100)}%` }} />
                    </div>
                    <strong>{item.count}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="feedback-evaluation">
            <div className="evaluation-heading">
              <h4>Feedback-based evaluation</h4>
              <span>{evaluation.verified_records} verified records</span>
            </div>
            <p>Positive class: <strong>Fraudulent</strong>. This is separate from held-out test-set metrics.</p>
            {evaluation.available ? (
              <>
                <div className="evaluation-metrics">
                  <div><span>Precision</span><strong>{(evaluation.precision * 100).toFixed(1)}%</strong></div>
                  <div><span>Recall</span><strong>{(evaluation.recall * 100).toFixed(1)}%</strong></div>
                  <div><span>F1-score</span><strong>{(evaluation.f1_score * 100).toFixed(1)}%</strong></div>
                </div>
                <div className="confusion-wrap">
                  <table className="feedback-confusion">
                    <caption>Rows are verified labels; columns are original model predictions.</caption>
                    <thead>
                      <tr><th scope="col">Actual / Predicted</th><th scope="col">Legitimate</th><th scope="col">Fraudulent</th></tr>
                    </thead>
                    <tbody>
                      <tr><th scope="row">Legitimate</th><td>{evaluation.true_negatives} (TN)</td><td>{evaluation.false_positives} (FP)</td></tr>
                      <tr><th scope="row">Fraudulent</th><td>{evaluation.false_negatives} (FN)</td><td>{evaluation.true_positives} (TP)</td></tr>
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="analytics-empty">Metrics are withheld until at least {evaluation.minimum_records} verified assessments include both legitimate and fraudulent ground-truth labels.</p>
            )}
          </div>
        </>
      )}
    </section>
  );
}

export default FeedbackAnalytics;