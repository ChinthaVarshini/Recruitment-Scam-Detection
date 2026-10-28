import { lazy, Suspense, useEffect, useRef, useState } from "react";

import "./App.css";
import BatchAnalysis from "./BatchAnalysis.jsx";
import FeedbackAnalytics from "./FeedbackAnalytics.jsx";
import ReviewerDesk from "./ReviewerDesk.jsx";
import SafeApplicationChecklist from "./SafeApplicationChecklist.jsx";

const RiskCharts = lazy(() => import("./RiskCharts.jsx"));
const API_URL = import.meta.env.VITE_API_URL || "/api";

function App() {
  const [form, setForm] = useState({
    title: "",
    location: "",
    company_profile: "",
    company_website: "",
    description: "",
    requirements: "",
    benefits: "",
  });

  const [result, setResult] = useState(null);
  const [history, setHistory] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("recruitmentguard-history")) || [];
    } catch {
      return [];
    }
  });
  const [selectedHistoryIds, setSelectedHistoryIds] = useState([]);
  const [historyStorageError, setHistoryStorageError] = useState("");
  const [loading, setLoading] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrStatus, setOcrStatus] = useState("");
  const [imagePreview, setImagePreview] = useState("");
  const [uploadType, setUploadType] = useState("");
  const [error, setError] = useState("");
  const [backendStatus, setBackendStatus] = useState("checking");
  const [scanStep, setScanStep] = useState(0);
  const [reviewerVisible, setReviewerVisible] = useState(false);
  const [feedbackLabel, setFeedbackLabel] = useState("");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [feedbackError, setFeedbackError] = useState("");
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const feedbackSubmitRef = useRef(false);
  const [jobUrl, setJobUrl] = useState("");
  const [urlScanning, setUrlScanning] = useState(false);
  const [urlScanError, setUrlScanError] = useState(null);
  const [scannedSourceUrl, setScannedSourceUrl] = useState("");
  const [urlTestInput, setUrlTestInput] = useState("");
  const [urlTesting, setUrlTesting] = useState(false);
  const [reportError, setReportError] = useState("");

  const updateHistory = (nextHistory) => {
    setHistory(nextHistory);
    try {
      localStorage.setItem("recruitmentguard-history", JSON.stringify(nextHistory));
      setHistoryStorageError("");
    } catch (storageError) {
      setHistoryStorageError(
        `Could not save scan history in this browser: ${storageError.message}`,
      );
    }
  };

  const recordAssessment = (assessment, jobSnapshot, title, sourceUrl = "") => {
    const analyzedAt = new Date();
    const historyId = globalThis.crypto?.randomUUID?.() ||
      `${analyzedAt.getTime()}-${Math.random().toString(16).slice(2)}`;
    const savedJob = Object.fromEntries(
      Object.entries(jobSnapshot).map(([key, value]) => [key, String(value || "").slice(0, 12000)]),
    );
    updateHistory([
      {
        historyId,
        analysisId: assessment.analysis_id,
        title: title || "Untitled job posting",
        riskLevel: assessment.risk_level,
        score: assessment.final_risk_score,
        prediction: assessment.prediction,
        analyzedAt: analyzedAt.toLocaleString(),
        sourceUrl,
        job: savedJob,
        assessment,
      },
      ...history,
    ].slice(0, 15));
  };

  const restoreHistoryEntry = (item) => {
    if (!item.assessment) return;
    setForm({
      title: item.job?.title || item.title || "",
      location: item.job?.location || "",
      company_profile: item.job?.company_profile || "",
      company_website: item.job?.company_website || "",
      description: item.job?.description || "",
      requirements: item.job?.requirements || "",
      benefits: item.job?.benefits || "",
    });
    setResult(item.assessment);
    setScannedSourceUrl(item.sourceUrl || "");
    setFeedbackLabel("");
    setFeedbackComment("");
    setFeedbackMessage("");
    setFeedbackError("");
    setFeedbackSubmitted(false);
    window.scrollTo({ top: document.querySelector(".result-panel")?.offsetTop || 0, behavior: "smooth" });
  };

  const toggleHistoryComparison = (historyId) => {
    setSelectedHistoryIds((previous) => (
      previous.includes(historyId)
        ? previous.filter((id) => id !== historyId)
        : previous.length < 2
          ? [...previous, historyId]
          : [previous[1], historyId]
    ));
  };

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((response) => {
        if (!response.ok) throw new Error("Backend unavailable");
        return response.json();
      })
      .then((data) => setBackendStatus(data.status === "healthy" ? "online" : "offline"))
      .catch(() => setBackendStatus("offline"));
  }, []);

  useEffect(() => {
    if (!loading) return undefined;
    const timer = setInterval(() => {
      setScanStep((step) => Math.min(step + 1, 3));
    }, 550);
    return () => clearInterval(timer);
  }, [loading]);

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError("");
    setOcrLoading(true);
    setOcrStatus("Reading image text...");
    setImagePreview(URL.createObjectURL(file));
    setUploadType(file.type);

    try {
      let extractedText = "";

      if (file.type === "application/pdf") {
        const pdfjsLib = await import("pdfjs-dist");
        const pdfWorker = (await import("pdfjs-dist/build/pdf.worker.min.mjs?url")).default;
        pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;
        setOcrStatus("Extracting PDF text...");
        const pdf = await pdfjsLib.getDocument({ data: await file.arrayBuffer() }).promise;
        const pageTexts = [];

        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
          const page = await pdf.getPage(pageNumber);
          const content = await page.getTextContent();
          pageTexts.push(content.items.map((item) => item.str).join(" "));
        }

        extractedText = pageTexts.join("\n").trim();

        if (!extractedText) {
          const { createWorker } = await import("tesseract.js");
          setOcrStatus("Scanned PDF detected. Running OCR...");
          const worker = await createWorker("eng");
          const scannedPages = [];

          for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
            const page = await pdf.getPage(pageNumber);
            const viewport = page.getViewport({ scale: 1.5 });
            const canvas = document.createElement("canvas");
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
            const { data } = await worker.recognize(canvas);
            scannedPages.push(data.text);
          }

          await worker.terminate();
          extractedText = scannedPages.join("\n").trim();
        }
      } else {
        const { createWorker } = await import("tesseract.js");
        const worker = await createWorker("eng");
        const { data } = await worker.recognize(file);
        await worker.terminate();
        extractedText = data.text.trim();
      }

      if (!extractedText) {
        throw new Error("No readable job description found in this file.");
      }

      setForm((previous) => ({
        ...previous,
        description: extractedText,
      }));
      setOcrStatus("Text extracted. Review it, then run analysis.");
    } catch (err) {
      setOcrStatus("");
      setError(err.message || "Could not read the uploaded image.");
    } finally {
      setOcrLoading(false);
      e.target.value = "";
    }
  };

  const loadDemo = () => {
    setForm({
      title: "Remote Data Entry Specialist",
      location: "Work from home",
      company_profile: "Global hiring team expanding quickly",
      company_website: "",
      description: "Earn weekly income with no experience required. Contact our hiring manager on WhatsApp to start immediately.",
      requirements: "No experience required. Must have a personal bank account.",
      benefits: "Flexible hours and fast payments.",
    });
    setResult(null);
    setError("");
  };

  const analyzeJob = async () => {
    setError("");
    setResult(null);

    const hasInput = Object.values(form).some(
      (value) => value.trim() !== ""
    );

    if (!hasInput) {
      setError("Please enter job posting information first.");
      return;
    }

    setLoading(true);
    setScanStep(0);

    try {
      const response = await fetch(`${API_URL}/predict`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Analysis failed.");
      }

      setResult(data);
      setFeedbackLabel("");
      setFeedbackComment("");
      setFeedbackMessage("");
      setFeedbackError("");
      setFeedbackSubmitted(false);
      recordAssessment(data, form, form.title.trim() || "Untitled job posting");
    } catch (err) {
      setError(
        `${err.message} Make sure the FastAPI backend is running on port 8000.`
      );
    } finally {
      setLoading(false);
    }
  };

  const scanJobUrl = async (event) => {
    event.preventDefault();
    setUrlScanError(null);
    setScannedSourceUrl("");
    setResult(null);
    if (!jobUrl.trim()) {
      setUrlScanError({ message: "Enter a job posting URL first." });
      return;
    }
    setUrlScanning(true);
    try {
      const response = await fetch(`${API_URL}/scan-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: jobUrl.trim() }),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = data.detail;
        throw Object.assign(
          new Error(
            typeof detail === "string"
              ? detail
              : detail?.message || "Could not scan this job page."
          ),
          { code: typeof detail === "object" ? detail.code : undefined }
        );
      }
      const { assessment, extracted_job: extractedJob } = data;
      setForm((previous) => ({
        ...previous,
        title: extractedJob.title || "",
        location: extractedJob.location || "",
        company_profile: extractedJob.company_profile || "",
        company_website: extractedJob.company_website || "",
        description: extractedJob.description || "",
        requirements: extractedJob.requirements || "",
        benefits: extractedJob.benefits || "",
      }));
      setResult(assessment);
      setScannedSourceUrl(data.source_url);
      setFeedbackLabel("");
      setFeedbackComment("");
      setFeedbackMessage("");
      setFeedbackError("");
      setFeedbackSubmitted(false);
      recordAssessment(
        assessment,
        {
          title: extractedJob.title || "",
          location: extractedJob.location || "",
          company_profile: extractedJob.company_profile || "",
          company_website: extractedJob.company_website || "",
          description: extractedJob.description || "",
          requirements: extractedJob.requirements || "",
          benefits: extractedJob.benefits || "",
        },
        extractedJob.title || "Scanned job posting",
        data.source_url,
      );
    } catch (requestError) {
      setUrlScanError({
        code: requestError.code,
        message: requestError.message,
      });
    } finally {
      setUrlScanning(false);
    }
  };

  const classifyUrlText = async (event) => {
    event.preventDefault();
    setUrlScanError(null);
    setScannedSourceUrl("");
    setResult(null);
    const urls = urlTestInput.split(/\r?\n/).map((url) => url.trim()).filter(Boolean);
    if (urls.length === 0) {
      setUrlScanError({ message: "Enter one or more URLs, one per line." });
      return;
    }

    setUrlTesting(true);
    try {
      const response = await fetch(`${API_URL}/classify-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls }),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = data.detail;
        throw new Error(
          typeof detail === "string"
            ? detail
            : detail?.message || "Could not classify these URLs."
        );
      }

      const assessment = data.assessment;
      setResult(assessment);
      setFeedbackLabel("");
      setFeedbackComment("");
      setFeedbackMessage("");
      setFeedbackError("");
      setFeedbackSubmitted(false);
      recordAssessment(
        assessment,
        {
          title: "URL-only test",
          description: urls.join("\n"),
        },
        "URL-only test",
      );
    } catch (requestError) {
      setUrlScanError({ message: requestError.message });
    } finally {
      setUrlTesting(false);
    }
  };

  const submitFeedback = async () => {
    if (feedbackSubmitRef.current || feedbackSubmitted || !result?.analysis_id || !feedbackLabel) return;
    setFeedbackError("");
    setFeedbackMessage("");
    feedbackSubmitRef.current = true;
    setFeedbackLoading(true);
    try {
      const response = await fetch(`${API_URL}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prediction_id: result.analysis_id,
          user_label: feedbackLabel,
          comment: feedbackComment,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not submit feedback.");
      setFeedbackMessage(data.message);
      setFeedbackSubmitted(true);
      setFeedbackComment("");
    } catch (requestError) {
      setFeedbackError(requestError.message);
    } finally {
      feedbackSubmitRef.current = false;
      setFeedbackLoading(false);
    }
  };

  const clearForm = () => {
    setForm({
      title: "",
      location: "",
      company_profile: "",
      company_website: "",
      description: "",
      requirements: "",
      benefits: "",
    });

    setResult(null);
    setError("");
  };

  const downloadReport = async () => {
    setReportError("");
    try {
      const { jsPDF } = await import("jspdf");
      const pdf = new jsPDF({ unit: "mm", format: "a4" });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 16;
      const contentWidth = pageWidth - margin * 2;
      let cursorY = 20;

      const addPageIfNeeded = (height) => {
        if (cursorY + height > pageHeight - margin) {
          pdf.addPage();
          cursorY = 20;
        }
      };

      const addSection = (heading) => {
        addPageIfNeeded(14);
        cursorY += 4;
        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(12);
        pdf.setTextColor(22, 91, 70);
        pdf.text(heading, margin, cursorY);
        cursorY += 7;
      };

      const addText = (value, options = {}) => {
        const text = String(value ?? "").trim();
        if (!text) return;
        const fontSize = options.fontSize || 10;
        const indent = options.indent || 0;
        const lineHeight = fontSize * 0.48;
        pdf.setFont("helvetica", options.bold ? "bold" : "normal");
        pdf.setFontSize(fontSize);
        pdf.setTextColor(48, 63, 59);
        const lines = pdf.splitTextToSize(text, contentWidth - indent);
        for (const line of lines) {
          addPageIfNeeded(lineHeight + 1);
          pdf.text(line, margin + indent, cursorY);
          cursorY += lineHeight;
        }
        cursorY += 2;
      };

      pdf.setFillColor(22, 91, 70);
      pdf.rect(0, 0, pageWidth, 39, "F");
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(19);
      pdf.setTextColor(255, 255, 255);
      pdf.text("RecruitmentGuard", margin, 17);
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(10);
      pdf.text("JOB POSTING SAFETY ASSESSMENT", margin, 25);
      pdf.text(`Generated ${new Date().toLocaleString()}`, margin, 32);
      cursorY = 49;

      addSection("Assessment Overview");
      addText(`Job: ${form.title.trim() || "Untitled job posting"}`, { bold: true });
      if (scannedSourceUrl) addText(`Scanned URL: ${scannedSourceUrl}`);
      if (result.url_test_mode) {
        addText("Mode: URL-only test. No website fetch or DNS lookup was performed.");
      }
      if (result.language_name) addText(`Detected language: ${result.language_name}`);
      addText(`Prediction: ${result.prediction || "Unavailable"}`);
      if (!result.model_supported && result.model_language_notice) {
        addText(result.model_language_notice);
      }
      addText(`Risk level: ${result.risk_level || "Unavailable"}`);
      addText(`Final risk score: ${result.final_risk_score ?? "—"}%`);
      addText(`Scam probability: ${result.model_supported ? `${result.scam_probability}%` : "Not assessed"}`);
      addText(`Confidence: ${result.model_supported ? `${result.confidence}%` : "Not assessed"}`);

      addSection("Risk Summary");
      addText(result.risk_summary?.message || "No summary available.");
      addText(
        `Detected indicators: ${result.risk_summary?.indicator_count ?? result.risk_indicators?.length ?? 0}; Critical: ${result.risk_summary?.critical_indicators ?? 0}; High: ${result.risk_summary?.high_indicators ?? 0}`,
      );

      addSection("Detected Warning Signs");
      if (result.risk_indicators?.length) {
        result.risk_indicators.forEach((indicator) => {
          addText(
            `${indicator.severity || "INFO"} - ${formatFeature(indicator.type)}: ${indicator.message}`,
            { indent: 3 },
          );
          if (indicator.evidence) {
            addText(`Matched text: ${indicator.evidence}`, { indent: 6, fontSize: 9 });
          }
        });
      } else {
        addText("No rule-based warning signs were detected. This does not guarantee the posting is safe.");
      }

      if (result.url_intelligence?.urls?.length) {
        addSection("URL Findings");
        result.url_intelligence.urls.forEach((item) => {
          addText(`${item.risk_level} URL risk (${item.url_risk_score}%): ${item.url}`);
          (item.findings || []).forEach((finding) => {
            addText(`- ${finding.message}`, { indent: 3, fontSize: 9 });
          });
        });
        addText(result.url_intelligence.domain_verification?.message || "");
      }

      addSection("Safety Recommendations");
      if (result.recommendations?.length) {
        result.recommendations.forEach((item, index) => {
          addText(`${index + 1}. ${item.action}`, { bold: true });
          addText(item.reason, { indent: 4 });
        });
      } else {
        addText("Verify the employer through independently found official contact information.");
      }
      addText(result.overall_advice || "");

      addPageIfNeeded(18);
      cursorY += 4;
      pdf.setDrawColor(190, 205, 199);
      pdf.line(margin, cursorY, pageWidth - margin, cursorY);
      cursorY += 7;
      addText(
        "Disclaimer: RecruitmentGuard provides decision support, not a guarantee of legitimacy. Independently verify employers and never pay recruitment fees.",
        { fontSize: 9 },
      );

      const safeTitle = (form.title.trim() || "job-assessment")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "")
        .slice(0, 48) || "job-assessment";
      pdf.save(`recruitmentguard-${safeTitle}.pdf`);
    } catch (reportGenerationError) {
      setReportError(
        `Could not create the PDF report: ${reportGenerationError.message || "unexpected error"}`,
      );
    }
  };

  const getRiskClass = (level) => {
    if (level === "NEEDS_REVIEW") return "medium";
    if (level === "CRITICAL") return "critical";
    if (level === "HIGH") return "high";
    if (level === "MEDIUM") return "medium";
    return "low";
  };

  const formatFeature = (feature) => {
    if (!feature) return "";

    return feature
      .replaceAll("_", " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  /* ================= CHART DATA ================= */

  const riskChartData = result
    ? [
        {
          name: "Risk",
          value: Number(result.final_risk_score) || 0,
          fill:
            result.risk_level === "CRITICAL"
              ? "#c7463f"
              : result.risk_level === "HIGH"
              ? "#d77835"
              : result.risk_level === "MEDIUM"
              ? "#c49b35"
              : "#579477",
        },
      ]
    : [];

  const scoreBreakdownData = result
    ? [
        {
          name: "ML Model",
          score: Number(result.ml_score) || 0,
        },
        {
          name: "Risk Indicators",
          score: Number(result.indicator_score) || 0,
        },
        {
          name: "Final Risk",
          score: Number(result.final_risk_score) || 0,
        },
      ]
    : [];

  const indicatorChartData = result
    ? ["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((severity) => ({
        name: severity,
        count:
          result.risk_indicators?.filter(
            (item) => item.severity === severity
          ).length || 0,
      }))
    : [];

  return (
    <div className="app">

      {/* ================= HEADER ================= */}

      <header className="navbar">
        <div className="brand">
          <div className="brand-icon">RG</div>

          <div>
            <h1>RecruitmentGuard</h1>
            <span>AI-Powered Recruitment Security</span>
          </div>
        </div>

        <div className="system-status">
          <span className={`status-dot ${backendStatus}`}></span>
          {backendStatus === "checking" ? "CHECKING API" : `AI MODEL ${backendStatus.toUpperCase()}`}
        </div>
        <button className="reviewer-toggle" type="button" onClick={() => setReviewerVisible((visible) => !visible)}>
          {reviewerVisible ? "Hide Reviewer Desk" : "Reviewer Desk"}
        </button>
      </header>

      <ReviewerDesk visible={reviewerVisible} onClose={() => setReviewerVisible(false)} />

      {/* ================= HERO ================= */}

      <section className="hero">

        <div className="hero-content">

          <div className="eyebrow">
            AI + NLP + MACHINE LEARNING
          </div>

          <h2>
            Detect Fake Jobs
            <span>Before You Apply.</span>
          </h2>

          <p>
            Analyze recruitment postings using machine learning,
            explainable AI, URL intelligence and multi-factor
            risk analysis.
          </p>

          <div className="hero-points">

            <div>
              <strong>01</strong>
              <span>AI Risk Detection</span>
            </div>

            <div>
              <strong>02</strong>
              <span>Explainable Results</span>
            </div>

            <div>
              <strong>03</strong>
              <span>Safety Recommendations</span>
            </div>

          </div>

          <div className="trust-strip">
            <div><strong>4</strong><span>signal layers</span></div>
            <div><strong>98%</strong><span>test accuracy</span></div>
            <div><strong>Local</strong><span>private processing</span></div>
          </div>

        </div>

        <div className="hero-card">

          <div className="shield">
            🛡️
          </div>

          <h3>Recruitment Safety</h3>

          <p>
            Protect yourself from fraudulent job offers,
            payment scams and suspicious application links.
          </p>

          <div className="security-line">
            <span></span>
            Multi-Factor Analysis Active
          </div>

        </div>

      </section>

      {history.length > 0 && (
        <section className="history-strip" aria-label="Recent analyses">
          <div className="history-heading">
            <div>
              <span className="history-kicker">SAVED IN THIS BROWSER</span>
              <h3>Scan history</h3>
            </div>
            <div className="history-actions">
              <span>Select two scans to compare</span>
              <button
                className="history-clear"
                onClick={() => {
                  updateHistory([]);
                  setSelectedHistoryIds([]);
                }}
                type="button"
              >
                Clear history
              </button>
            </div>
          </div>
          <div className="history-list">
            {history.map((item, index) => (
              <div className="history-item" key={item.historyId || `${item.analyzedAt}-${index}`}>
                <span className={`history-status ${getRiskClass(item.riskLevel)}`}></span>
                <div>
                  <strong>{item.title}</strong>
                  <small>{item.analyzedAt}</small>
                </div>
                <b className={getRiskClass(item.riskLevel)}>{item.score == null ? "Review" : `${item.score}%`}</b>
                <div className="history-item-actions">
                  <button
                    type="button"
                    onClick={() => restoreHistoryEntry(item)}
                    disabled={!item.assessment}
                  >
                    {item.assessment ? "View" : "Unavailable"}
                  </button>
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedHistoryIds.includes(item.historyId)}
                      onChange={() => toggleHistoryComparison(item.historyId)}
                      disabled={!item.historyId && !item.assessment}
                      aria-label={`Select ${item.title} to compare`}
                    />
                    Compare
                  </label>
                </div>
              </div>
            ))}
          </div>
          {historyStorageError && <p className="batch-error" role="alert">{historyStorageError}</p>}
          {selectedHistoryIds.length === 2 && (() => {
            const [first, second] = selectedHistoryIds.map(
              (historyId) => history.find((item) => item.historyId === historyId),
            );
            if (!first || !second) return null;
            return (
              <div className="history-comparison" aria-live="polite">
                <h4>Assessment comparison</h4>
                <table>
                  <thead>
                    <tr><th>Measure</th><th>{first.title}</th><th>{second.title}</th></tr>
                  </thead>
                  <tbody>
                    <tr><th>Risk level</th><td>{first.riskLevel || "—"}</td><td>{second.riskLevel || "—"}</td></tr>
                    <tr><th>Risk score</th><td>{first.score == null ? "Not assessed" : `${first.score}%`}</td><td>{second.score == null ? "Not assessed" : `${second.score}%`}</td></tr>
                    <tr><th>Prediction</th><td>{first.prediction || "—"}</td><td>{second.prediction || "—"}</td></tr>
                    <tr><th>Warning signs</th><td>{first.assessment?.risk_indicators?.length ?? "—"}</td><td>{second.assessment?.risk_indicators?.length ?? "—"}</td></tr>
                    <tr><th>Scanned</th><td>{first.analyzedAt}</td><td>{second.analyzedAt}</td></tr>
                  </tbody>
                </table>
              </div>
            );
          })()}
        </section>
      )}

      {/* ================= MAIN ================= */}

      <main className="dashboard">

        <FeedbackAnalytics />

        {/* ================= INPUT ================= */}

        <section className="panel input-panel">

          <div className="section-heading">

            <div className="number">
              01
            </div>

            <div>
              <h3>Job Posting Analysis</h3>

              <p>
                Enter job details in English, Hindi, or Telugu. Hindi/Telugu results use phrase checks, not the English-trained ML model.
              </p>
            </div>

          </div>

          <form className="job-url-scanner" onSubmit={scanJobUrl}>
            <div className="job-url-copy">
              <strong>Scan a public job posting URL</strong>
              <span>We extract available job details and run the same risk analysis. Review extracted fields below.</span>
            </div>
            <div className="job-url-controls">
              <input
                aria-label="Job posting URL"
                type="url"
                inputMode="url"
                autoComplete="url"
                maxLength={2048}
                placeholder="https://example.com/jobs/role"
                value={jobUrl}
                onChange={(event) => setJobUrl(event.target.value)}
                disabled={urlScanning || urlTesting}
              />
              <button type="submit" disabled={urlScanning || urlTesting || loading || !jobUrl.trim()}>
                {urlScanning ? "Scanning page..." : "Scan URL"}
              </button>
            </div>
            <p className="job-url-privacy">
              Public HTTP/HTTPS pages only. Private/local addresses, non-standard ports, redirects to private networks, and pages over 2 MB are blocked. The page is fetched by your API server.
            </p>
            {urlScanError && (
              <div className="job-url-error" role="alert">
                {urlScanError.code === "hostname_unresolved" ? (
                  <>
                    <strong>Unable to Scan — hostname could not be resolved</strong>
                    <span>{urlScanError.message}</span>
                    <span>DNS failure means the page could not be scanned; it is not evidence that the URL is fraudulent.</span>
                  </>
                ) : (
                  <span>{urlScanError.message}</span>
                )}
              </div>
            )}
            {scannedSourceUrl && (
              <p className="job-url-success" role="status">
                Scanned: <a href={scannedSourceUrl} target="_blank" rel="noreferrer">{scannedSourceUrl}</a>
              </p>
            )}
          </form>

          <form className="job-url-scanner url-classifier" onSubmit={classifyUrlText}>
            <div className="job-url-copy">
              <strong>URL-only test mode (no website fetch)</strong>
              <span>Run URL feature extraction and the existing ML model directly on URL strings. Enter one URL per line; DNS and page availability are not checked.</span>
            </div>
            <textarea
              aria-label="URLs for direct classification"
              maxLength={40960}
              placeholder={"https://example.com/jobs/role\nhttps://suspicious-site.xyz/register"}
              value={urlTestInput}
              onChange={(event) => setUrlTestInput(event.target.value)}
              disabled={urlTesting || urlScanning}
              rows={3}
            />
            <div className="job-url-controls">
              <button type="submit" disabled={urlTesting || urlScanning || loading || !urlTestInput.trim()}>
                {urlTesting ? "Classifying..." : "Classify URL text"}
              </button>
            </div>
          </form>

          <BatchAnalysis apiUrl={API_URL} />

          <div className="upload-zone">
            <div className="upload-icon">+</div>
            <div className="upload-copy">
              <strong>Scan a job post file</strong>
              <span>Upload a job post image or PDF and we will extract the description automatically.</span>
            </div>
            <label className="upload-button">
              {ocrLoading ? "Reading..." : "Upload image"}
              <input type="file" accept="image/*,.pdf,application/pdf" onChange={handleImageUpload} disabled={ocrLoading} />
            </label>
            <button className="demo-button" onClick={loadDemo} type="button">
              Load demo
            </button>
          </div>

          {imagePreview && (
            <div className="upload-result">
              {uploadType === "application/pdf" ? (
                <div className="pdf-preview">PDF</div>
              ) : (
                <img src={imagePreview} alt="Uploaded job posting preview" />
              )}
              <div>
                <strong>{ocrLoading ? "Extracting text with OCR" : "Screenshot ready"}</strong>
                <span>{ocrStatus}</span>
              </div>
            </div>
          )}

          <div className="form-grid">

            <div className="field">

              <label>Job Title</label>

              <input
                name="title"
                value={form.title}
                onChange={handleChange}
                placeholder="e.g. Software Engineer"
              />

            </div>

            <div className="field">

              <label>Location</label>

              <input
                name="location"
                value={form.location}
                onChange={handleChange}
                placeholder="e.g. Hyderabad / Remote"
              />

            </div>

            <div className="field full">

              <label>Company Profile</label>

              <textarea
                name="company_profile"
                value={form.company_profile}
                onChange={handleChange}
                placeholder="Enter company information..."
                rows="4"
              />

            </div>

            <div className="field full">

              <label>Employer Official Website</label>

              <input
                name="company_website"
                value={form.company_website}
                onChange={handleChange}
                placeholder="e.g. https://company.com"
                type="url"
              />

            </div>

            <div className="field full">

              <label>Job Description</label>

              <textarea
                name="description"
                value={form.description}
                onChange={handleChange}
                placeholder="Paste the complete job description here..."
                rows="7"
              />

            </div>

            <div className="field">

              <label>Requirements</label>

              <textarea
                name="requirements"
                value={form.requirements}
                onChange={handleChange}
                placeholder="Skills, experience, education..."
                rows="5"
              />

            </div>

            <div className="field">

              <label>Benefits</label>

              <textarea
                name="benefits"
                value={form.benefits}
                onChange={handleChange}
                placeholder="Salary, benefits, work arrangement..."
                rows="5"
              />

            </div>

          </div>

          {error && (
            <div className="error-box">
              ⚠️ {error}
            </div>
          )}

          <div className="form-actions">

            <button
              className="clear-button"
              onClick={clearForm}
            >
              Clear
            </button>

            <button
              className="analyze-button"
              onClick={analyzeJob}
              disabled={loading || urlScanning}
            >

              {loading ? (
                <>
                  <span className="spinner"></span>
                  Analyzing...
                </>
              ) : (
                <>
                  Analyze Job
                  <span>→</span>
                </>
              )}

            </button>

          </div>

        </section>

        {/* ================= RESULT ================= */}

        <section className="panel result-panel">

          <div className="section-heading">

            <div className="number">
              02
            </div>

            <div>
              <h3>Risk Assessment</h3>

              <p>
                AI prediction and explanation
              </p>
            </div>

          </div>

          {/* EMPTY */}

          {!result && !loading && (

            <div className="empty-result">

              <div className="empty-icon">
                ◉
              </div>

              <h3>
                Waiting for analysis
              </h3>

              <p>
                Enter a job posting and click
                <strong> Analyze Job </strong>
                to see the AI assessment.
              </p>

            </div>

          )}

          {/* LOADING */}

          {loading && (

            <div className="empty-result">

              <div className="loading-ring"></div>

              <h3>
                Analyzing Job Posting
              </h3>

              <p>
                Running NLP, machine learning,
                risk indicators and URL intelligence...
              </p>

              <div className="scan-steps">
                {["Parsing job content", "Scoring language signals", "Checking risk indicators", "Preparing recommendations"].map((step, index) => (
                  <div className={index <= scanStep ? "complete" : ""} key={step}>
                    <span>{index <= scanStep ? "✓" : index + 1}</span>
                    {step}
                  </div>
                ))}
              </div>

            </div>

          )}

          {/* RESULTS */}

          {result && !loading && (

            <div className="results">
              {result.model_supported === false && (
                <p className="url-test-notice" role="status">
                  {result.model_language_notice}
                </p>
              )}
              {result.url_test_mode && (
                <p className="url-test-notice" role="status">
                  URL-only test: no DNS lookup or website fetch was performed. {result.url_test_notice}
                </p>
              )}

              {/* ================= TOP RISK ================= */}

              <div
                className={`risk-banner ${getRiskClass(
                  result.risk_level
                )}`}
              >

                <div className="risk-symbol">

                  {result.risk_level === "CRITICAL"
                    ? "!"
                    : result.risk_level === "HIGH"
                    ? "!"
                    : "✓"}

                </div>

                <div className="risk-main">

                  <span>
                    FINAL RISK SCORE
                  </span>

                  <strong>
                    {result.final_risk_score == null ? "Not assessed" : `${result.final_risk_score}%`}
                  </strong>

                  <small>
                    {result.risk_level === "NEEDS_REVIEW" ? "NEEDS REVIEW" : `${result.risk_level} RISK`}
                  </small>

                </div>

                <div className="confidence">

                  <span>
                    Confidence
                  </span>

                  <strong>
                    {result.model_supported === false ? "Not assessed" : `${result.confidence}%`}
                  </strong>

                </div>

              </div>

              {/* ================= RISK GRAPH ================= */}

              <div className="result-section">

                <h4>
                  Risk Visualization
                </h4>

                <div className="charts-grid">

                  <Suspense fallback={<div className="charts-grid" aria-hidden="true" />}>
                    <RiskCharts
                      kind="risk"
                      riskChartData={riskChartData}
                      scoreBreakdownData={scoreBreakdownData}
                      score={result.final_risk_score}
                    />
                  </Suspense>

                </div>

              </div>

              {/* ================= SCORE BREAKDOWN ================= */}

              <div className="result-section">

                <h4>
                  Risk Score Breakdown
                </h4>

                <div className="score-grid">

                  <div className="score-card">

                    <div className="score-card-top">

                      <span>
                        ML Model
                      </span>

                      <strong>
                        {result.model_supported === false ? "Not assessed" : `${result.ml_score}%`}
                      </strong>

                    </div>

                    <div className="progress">

                      <div
                        style={{
                          width: `${Number(result.ml_score) || 0}%`,
                        }}
                      ></div>

                    </div>

                    <small>
                      {result.model_supported === false
                        ? "Not used for this language"
                        : `Weight: ${result.risk_weights?.ml_model ?? 70}%`}
                    </small>

                  </div>

                  <div className="score-card">

                    <div className="score-card-top">

                      <span>
                        Risk Indicators
                      </span>

                      <strong>
                        {result.indicator_score}%
                      </strong>

                    </div>

                    <div className="progress">

                      <div
                        style={{
                          width: `${result.indicator_score}%`,
                        }}
                      ></div>

                    </div>

                    <small>
                      Weight:{" "}
                      {result.risk_weights?.risk_indicators ??
                        30}
                      %
                    </small>

                  </div>

                </div>

              </div>

              {/* ================= MODEL RESULT ================= */}

              <div className="prediction-card">

                <div>

                  <span>
                    {result.model_supported === false ? "LANGUAGE CHECK STATUS" : "MODEL PREDICTION"}
                  </span>

                  <strong>
                    {result.prediction === "NEEDS_REVIEW" ? "NEEDS REVIEW" : result.prediction}
                  </strong>

                </div>

                <div className="prediction-probability">

                  <span>
                    SCAM PROBABILITY
                  </span>

                  <strong>
                    {result.model_supported === false ? "Not assessed" : `${result.scam_probability}%`}
                  </strong>

                </div>

              </div>

              {/* ================= INDICATOR GRAPH ================= */}

              {result.risk_indicators?.length > 0 && (

                <div className="result-section">

                  <h4>
                    Risk Indicator Distribution
                  </h4>

                  <Suspense fallback={<div className="chart-card indicator-chart" aria-hidden="true" />}>
                    <RiskCharts kind="indicators" indicatorChartData={indicatorChartData} />
                  </Suspense>

                </div>

              )}

              {/* ================= INDICATORS ================= */}

              {result.risk_indicators?.length > 0 && (

                <div className="result-section">

                  <h4>
                    ⚠️ Detected Risk Indicators
                  </h4>

                  <div className="indicator-list">

                    {result.risk_indicators.map(
                      (indicator, index) => (

                        <div
                          className={`indicator ${indicator.severity.toLowerCase()}`}
                          key={index}
                        >

                          <div className="indicator-header">

                            <strong>
                              {indicator.severity}
                            </strong>

                            <span>
                              {formatFeature(
                                indicator.type
                              )}
                            </span>

                          </div>

                          <p>
                            {indicator.message}
                          </p>
                          {indicator.evidence && (
                            <p className="indicator-evidence">
                              Matched text: <mark>{indicator.evidence}</mark>
                            </p>
                          )}

                        </div>

                      )
                    )}

                  </div>

                </div>

              )}

              {/* ================= WHY ================= */}

              {(result.fraud_reasons?.length > 0 ||
                result.legitimate_reasons?.length > 0) && (

                <div className="result-section">

                  <h4>
                    🔎 Why This Prediction?
                  </h4>

                  <div className="reason-columns">

                    <div className="reason-box fraud">

                      <h5>
                        ⚠ Fraud Signals
                      </h5>

                      {result.fraud_reasons
                        ?.slice(0, 6)
                        .map((item, index) => (

                          <div
                            className="reason-row"
                            key={index}
                          >

                            <span>
                              {item.feature}
                            </span>

                            <strong>
                              +
                              {Number(
                                item.contribution
                              ).toFixed(3)}
                            </strong>

                          </div>

                        ))}

                    </div>

                    <div className="reason-box legitimate">

                      <h5>
                        ✓ Legitimate Signals
                      </h5>

                      {result.legitimate_reasons
                        ?.slice(0, 6)
                        .map((item, index) => (

                          <div
                            className="reason-row"
                            key={index}
                          >

                            <span>
                              {item.feature}
                            </span>

                            <strong>
                              {Number(
                                item.contribution
                              ).toFixed(3)}
                            </strong>

                          </div>

                        ))}

                    </div>

                  </div>

                </div>

              )}

              {/* ================= URL INTELLIGENCE ================= */}

              {result.url_intelligence && (

                  <div className="result-section">

                    <h4>
                      🔗 URL Intelligence
                    </h4>

                    {result.url_intelligence.domain_verification && (
                      <div className={`domain-verification ${result.url_intelligence.domain_verification.status.toLowerCase()}`}>
                        <div>
                          <strong>Employer domain check</strong>
                          <span>{result.url_intelligence.domain_verification.message}</span>
                        </div>
                        {result.url_intelligence.domain_verification.official_domain && (
                          <small>Official domain: {result.url_intelligence.domain_verification.official_domain}</small>
                        )}
                      </div>
                    )}

                    {result.url_intelligence.urls_detected > 0 ? (
                    <div className="url-summary">

                      <div>

                        <span>
                          URLs Detected
                        </span>

                        <strong>
                          {
                            result.url_intelligence
                              .urls_detected
                          }
                        </strong>

                      </div>

                      <div>

                        <span>
                          URL Risk
                        </span>

                        <strong>
                          {
                            result.url_intelligence
                              .overall_url_risk
                          }
                          %
                        </strong>

                      </div>

                      <div>

                        <span>
                          Risk Level
                        </span>

                        <strong>
                          {
                            result.url_intelligence
                              .risk_level
                          }
                        </strong>

                      </div>

                    </div>
                    ) : (
                      <p className="no-url-message">No application URLs were found in this posting.</p>
                    )}

                    {result.url_intelligence.urls.map(
                      (url, index) => (

                        <div
                          className="url-card"
                          key={index}
                        >

                          <div className="url-top">

                            <strong>
                              {url.domain}
                            </strong>

                            <span
                              className={getRiskClass(
                                url.risk_level
                              )}
                            >
                              {url.risk_level}
                            </span>

                          </div>

                          <p>
                            {url.url}
                          </p>

                          {url.findings?.map(
                            (
                              finding,
                              findingIndex
                            ) => (

                              <div
                                className="url-finding"
                                key={
                                  findingIndex
                                }
                              >

                                <strong>
                                  {finding.severity}
                                </strong>

                                <span>
                                  {finding.message}
                                </span>

                              </div>

                            )
                          )}

                        </div>

                      )
                    )}

                  </div>

                )}

              {/* ================= RECOMMENDATIONS ================= */}

              {result.recommendations?.length >
                0 && (

                <div className="result-section">

                  <h4>
                    🛡️ Safety Recommendations
                  </h4>

                  <div className="recommendation-list">

                    {result.recommendations.map(
                      (item, index) => (

                        <div
                          className="recommendation"
                          key={index}
                        >

                          <div className="recommendation-number">
                            {index + 1}
                          </div>

                          <div>

                            <strong>
                              {item.action}
                            </strong>

                            <p>
                              {item.reason}
                            </p>

                          </div>

                        </div>

                      )
                    )}

                  </div>

                  {result.overall_advice && (

                    <div className="overall-advice">

                      <strong>
                        Overall Advice
                      </strong>

                      <p>
                        {result.overall_advice}
                      </p>

                    </div>

                  )}

                </div>

              )}

              {/* ================= SUMMARY ================= */}

              {result.risk_summary && (

                <div className="summary-box">

                  <strong>
                    Risk Assessment Summary
                  </strong>

                  <p>
                    {result.risk_summary.message}
                  </p>

                  <div className="summary-stats">

                    <span>
                      Indicators:
                      <strong>
                        {
                          result.risk_summary
                            .indicator_count
                        }
                      </strong>
                    </span>

                    <span>
                      Critical:
                      <strong>
                        {
                          result.risk_summary
                            .critical_indicators
                        }
                      </strong>
                    </span>

                    <span>
                      High:
                      <strong>
                        {
                          result.risk_summary
                            .high_indicators
                        }
                      </strong>
                    </span>

                  </div>

                  <button className="report-button" onClick={downloadReport} type="button">
                    Download PDF assessment report
                  </button>
                  {reportError && <p className="job-url-error" role="alert">{reportError}</p>}

                </div>

              )}

              <SafeApplicationChecklist
                key={`safe-checklist:${encodeURIComponent(
                  (scannedSourceUrl || `${form.title}|${form.company_profile}`)
                    .trim()
                    .toLowerCase(),
                ).slice(0, 180)}`}
                storageKey={`recruitmentguard-safe-checklist:${encodeURIComponent(
                  (scannedSourceUrl || `${form.title}|${form.company_profile}`)
                    .trim()
                    .toLowerCase(),
                ).slice(0, 180)}`}
              />

              {result.analysis_id && <div className="result-section feedback-section">
                <h4>Was this assessment accurate?</h4>
                <p>Your label is a suggestion, not a verified ground-truth label. Feedback is saved for independent review and never triggers automatic retraining.</p>
                <div className="feedback-actions">
                  <label>
                    Your assessment
                    <select value={feedbackLabel} onChange={(event) => setFeedbackLabel(event.target.value)} disabled={feedbackSubmitted} required>
                      <option value="">Choose a label</option>
                      <option value="FRAUDULENT">This job is fraudulent</option>
                      <option value="LEGITIMATE">This job is legitimate</option>
                    </select>
                  </label>
                  <label className="feedback-comment">
                    Optional explanation
                    <textarea
                      value={feedbackComment}
                      onChange={(event) => setFeedbackComment(event.target.value)}
                      maxLength={1000}
                      placeholder="What did the assessment miss?"
                      rows={2}
                      disabled={feedbackSubmitted}
                    />
                  </label>
                  <button type="button" onClick={submitFeedback} disabled={!feedbackLabel || feedbackLoading || feedbackSubmitted}>
                    {feedbackLoading ? "Saving..." : feedbackSubmitted ? "Feedback saved" : "Send feedback"}
                  </button>
                </div>
                {feedbackMessage && <p className="feedback-success" role="status">{feedbackMessage}</p>}
                {feedbackError && <p className="feedback-error" role="alert">{feedbackError}</p>}
              </div>}

            </div>

          )}

        </section>

      </main>

      {/* ================= FOOTER ================= */}

      <footer>

        <div>

          <strong>
            RecruitmentGuard
          </strong>

          <span>
            AI-powered recruitment scam detection
          </span>

        </div>

        <span>
          TF-IDF · Logistic Regression · Explainable AI ·
          Multi-Factor Risk Engine
        </span>

      </footer>

    </div>
  );
}

export default App;