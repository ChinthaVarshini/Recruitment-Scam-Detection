const pageUrl = document.getElementById("page-url");
const scanButton = document.getElementById("scan-button");
const status = document.getElementById("status");
const result = document.getElementById("result");
const riskBanner = document.getElementById("risk-banner");

let activeUrl = "";
let supportedPage = false;
let activeTabId = null;

function setStatus(message, isError = false) {
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function showError(message) {
  result.hidden = true;
  setStatus(message, true);
}

async function loadActiveTab() {
  try {
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    activeTabId = tab?.id ?? null;
    activeUrl = tab?.url || "";
    pageUrl.textContent = activeUrl || "No active page URL is available.";

    supportedPage = Boolean(
      activeTabId !== null && RecruitmentGuardApi.isSupportedPageUrl(activeUrl),
    );
    scanButton.disabled = !supportedPage;
    if (!supportedPage) {
      setStatus("Open a public HTTP or HTTPS job page before scanning.", true);
    }
  } catch {
    pageUrl.textContent = "Could not read the active tab.";
    setStatus("Allow the extension to access the active tab, then try again.", true);
  }
}

function displayAssessment(data) {
  const assessment = data.assessment;
  const extractedJob = data.extracted_job || {};
  const riskLevel = String(assessment.risk_level || "UNKNOWN").toLowerCase();

  document.getElementById("risk-label").textContent =
    `${assessment.risk_level || "UNKNOWN"} RISK`;
  document.getElementById("risk-score").textContent =
    `${assessment.final_risk_score ?? "—"}%`;
  riskBanner.className = `risk-banner ${riskLevel}`;
  document.getElementById("job-title").textContent =
    extractedJob.title || "Job details extracted";
  document.getElementById("company-name").textContent =
    extractedJob.company_profile || extractedJob.company_website || "";
  document.getElementById("prediction").textContent =
    `Model result: ${assessment.prediction || "Unavailable"}`;
  document.getElementById("risk-summary").textContent =
    assessment.risk_summary?.message ||
    assessment.overall_advice ||
    "Review the full assessment and verify the employer independently.";

  const evidenceSection = document.getElementById("evidence-section");
  const evidenceList = document.getElementById("evidence-list");
  evidenceList.replaceChildren();
  for (const indicator of assessment.risk_indicators || []) {
    const item = document.createElement("li");
    item.append(`${indicator.severity || "INFO"}: ${indicator.message || "Warning sign detected."}`);
    if (indicator.evidence) {
      item.append(" Matched text: ");
      const matchedText = document.createElement("mark");
      matchedText.textContent = indicator.evidence;
      item.append(matchedText);
    }
    evidenceList.append(item);
  }
  evidenceSection.hidden = evidenceList.childElementCount === 0;

  result.hidden = false;
  setStatus("Scan complete. Review the warning signs and matched job text.");
}

async function scanActiveJob() {
  scanButton.disabled = true;
  result.hidden = true;
  setStatus("Reading visible page text…");
  try {
    const [page] = await chrome.scripting.executeScript({
      target: { tabId: activeTabId },
      func: () => ({
        url: window.location.href,
        title: document.title,
        text: document.body?.innerText?.slice(0, 20000) || "",
      }),
    });
    const visiblePage = page?.result;
    const validationMessage = RecruitmentGuardApi.validatePageContent(visiblePage);
    if (validationMessage) {
      throw new Error(validationMessage);
    }

    visiblePage.text = visiblePage.text.slice(0, 20000);
    setStatus("Analyzing with RecruitmentGuard… This may take a moment.");
    const data = await RecruitmentGuardApi.scanPageContent(visiblePage);
    displayAssessment({
      ...data,
      extracted_job: {
        title: data.page_title || "Visible page content",
      },
    });
  } catch (error) {
    const message = error.message ||
      "Could not read this page. Open a normal public web page and try again.";
    showError(message);
  } finally {
    scanButton.disabled = !supportedPage;
  }
}

scanButton.addEventListener("click", scanActiveJob);
loadActiveTab();
