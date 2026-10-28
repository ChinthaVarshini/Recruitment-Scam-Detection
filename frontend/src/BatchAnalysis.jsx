import { useRef, useState } from "react";

const MAX_CSV_BYTES = 1_000_000;
const COLUMNS = [
  "title",
  "company",
  "location",
  "prediction",
  "risk_level",
  "final_risk_score",
  "fraud_probability",
  "risk_indicators",
  "top_fraud_signals",
  "duplicate_matches",
  "error",
];

function csvCell(value) {
  let text = String(value ?? "");
  if (/^[\s]*[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

function downloadCsv(rows, filename) {
  const content = [
    COLUMNS.map(csvCell).join(","),
    ...rows.map((row) => [
      row.title,
      row.company,
      row.location,
      row.prediction,
      row.risk_level,
      row.final_risk_score,
      row.fraud_probability,
      (row.risk_indicators || []).map((item) => `${item.severity}: ${item.type}`).join("; "),
      (row.fraud_reasons || []).map((item) => item.feature).join("; "),
      (row.duplicate_matches || []).map((item) => `${item.match_type} with row ${item.row_number} (${item.similarity}%)`).join("; "),
      row.error,
    ].map(csvCell).join(",")),
  ].join("\r\n");
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadTemplate() {
  const example = [
    ["title", "company", "location", "description", "requirements", "benefits"],
    ["Software Engineer", "Example Company", "Hyderabad", "Build web applications with our team.", "Python and two years experience", "Salary and health insurance"],
  ].map((row) => row.map(csvCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([example], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "recruitmentguard-batch-template.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function BatchAnalysis({ apiUrl }) {
  const fileInput = useRef(null);
  const [file, setFile] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const analyzeBatch = async (event) => {
    event.preventDefault();
    setError("");
    setReport(null);
    if (!file) {
      setError("Choose a CSV file to analyze.");
      return;
    }
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Please choose a .csv file.");
      return;
    }
    if (file.size > MAX_CSV_BYTES) {
      setError("CSV file must be 1 MB or smaller.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/batch-predict`, {
        method: "POST",
        headers: { "Content-Type": "text/csv" },
        body: await file.text(),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Batch analysis failed.");
      setReport(data);
    } catch (requestError) {
      setError(`${requestError.message} Make sure the FastAPI backend is running.`);
    } finally {
      setLoading(false);
    }
  };

  const analyzedRows = report?.results.filter((row) => row.status === "ANALYZED") || [];
  const highRiskRows = analyzedRows.filter((row) => ["HIGH", "CRITICAL"].includes(row.risk_level));
  const duplicateRows = analyzedRows.filter((row) => row.duplicate_matches?.length);

  return (
    <section className="batch-analysis" aria-labelledby="batch-analysis-title">
      <div className="batch-heading">
        <div>
          <span className="batch-kicker">MULTIPLE POSTINGS</span>
          <h3 id="batch-analysis-title">Batch job analysis</h3>
          <p>Upload a CSV to analyze up to 250 job postings and find duplicates or similar warning patterns.</p>
        </div>
        <button className="batch-template" type="button" onClick={downloadTemplate}>
          Download CSV template
        </button>
      </div>
      <form className="batch-form" onSubmit={analyzeBatch}>
        <label className="batch-file-label">
          Choose job-post CSV
          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              setFile(event.target.files?.[0] || null);
              setReport(null);
              setError("");
            }}
            disabled={loading}
          />
        </label>
        <span className="batch-file-name">{file ? `${file.name} (${(file.size / 1024).toFixed(1)} KB)` : "No file selected"}</span>
        <button className="batch-submit" type="submit" disabled={loading || !file}>
          {loading ? "Analyzing CSV..." : "Analyze CSV"}
        </button>
      </form>
      <p className="batch-guidance">
        Recognized columns include title, company, location, description/job_description/combined_text, requirements, benefits, and company_website. UTF-8 CSV only; maximum 1 MB. Invalid rows are reported individually.
      </p>
      {error && <p className="batch-error" role="alert">{error}</p>}
      {report && (
        <div className="batch-report" aria-live="polite">
          <div className="batch-summary">
            <div><span>Rows</span><strong>{report.total_rows}</strong></div>
            <div><span>Analyzed</span><strong>{report.analyzed_count}</strong></div>
            <div><span>High risk</span><strong>{report.high_risk_count}</strong></div>
            <div><span>Duplicate pairs</span><strong>{report.duplicate_pair_count || 0}</strong></div>
            <div><span>Invalid</span><strong>{report.invalid_count}</strong></div>
          </div>
          <div className="batch-export-actions">
            <button type="button" onClick={() => downloadCsv(analyzedRows, "recruitmentguard-batch-results.csv")} disabled={!analyzedRows.length}>
              Export analyzed results
            </button>
            <button type="button" onClick={() => downloadCsv(highRiskRows, "recruitmentguard-high-risk-jobs.csv")} disabled={!highRiskRows.length}>
              Export high-risk jobs
            </button>
            <button type="button" onClick={() => downloadCsv(duplicateRows, "recruitmentguard-duplicate-jobs.csv")} disabled={!duplicateRows.length}>
              Export duplicate matches
            </button>
            <button type="button" onClick={() => downloadCsv(report.results, "recruitmentguard-batch-all-rows.csv")}>
              Export all rows &amp; errors
            </button>
          </div>
          <div className="batch-table-wrap">
            <table className="batch-table">
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Job title</th>
                  <th>Prediction</th>
                  <th>Risk</th>
                  <th>Score</th>
                  <th>Duplicate match</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {report.results.map((row) => (
                  <tr key={`${row.row_number}-${row.title}`}>
                    <td>{row.row_number}</td>
                    <td>{row.title}</td>
                    <td>{row.prediction || "—"}</td>
                    <td>{row.risk_level || "—"}</td>
                    <td>{row.final_risk_score == null ? "—" : `${row.final_risk_score}%`}</td>
                    <td>
                      {row.duplicate_matches?.length
                        ? row.duplicate_matches.map((match) => (
                          <span className="duplicate-match" key={`${match.row_number}-${match.match_type}`}>
                            {match.match_type.replaceAll("_", " ")}: row {match.row_number} ({match.similarity}%)
                          </span>
                        ))
                        : "—"}
                    </td>
                    <td>{row.status === "ANALYZED" ? "Analyzed" : row.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="batch-disclaimer">
            This is decision support, not a guarantee. Check extracted data and verify employers independently.
          </p>
        </div>
      )}
    </section>
  );
}

export default BatchAnalysis;
