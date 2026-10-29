(function () {
  const API_URL = "https://recruitment-scam-detection.onrender.com";
  const REQUEST_TIMEOUT_MS = 90000;

  function isSupportedPageUrl(pageUrl) {
    try {
      return ["http:", "https:"].includes(new URL(pageUrl).protocol);
    } catch {
      return false;
    }
  }

  function validatePageContent(page) {
    if (!page || !isSupportedPageUrl(page.url)) {
      return "Open a public HTTP or HTTPS job page before scanning.";
    }
    if (typeof page.text !== "string" || !page.text.trim()) {
      return "No readable page text was found. Open the job details or offer message and try again.";
    }
    return "";
  }

  async function readJsonResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    const isJson =
      /application\/json/i.test(contentType) || /\+json/i.test(contentType);

    if (!isJson) {
      const body = (await response.text()).trim().replace(/\s+/g, " ");
      const details = body ? ` ${body.slice(0, 200)}` : "";
      throw new Error(
        `RecruitmentGuard returned an unexpected response (HTTP ${response.status}, ${contentType || "unknown content type"}).${details}`,
      );
    }

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error("RecruitmentGuard returned an invalid response. Please try again.");
    }

    if (!response.ok) {
      const detail = data && typeof data === "object" ? data.detail : null;
      const message =
        typeof detail === "string"
          ? detail
          : detail?.message || data?.message;
      throw new Error(
        message || `RecruitmentGuard could not scan this page (HTTP ${response.status}).`,
      );
    }

    if (
      !data ||
      typeof data !== "object" ||
      !data.assessment ||
      typeof data.assessment !== "object" ||
      typeof data.assessment.risk_level !== "string" ||
      typeof data.assessment.final_risk_score !== "number" ||
      !Array.isArray(data.assessment.risk_indicators)
    ) {
      throw new Error("RecruitmentGuard returned incomplete scan results. Please try again.");
    }

    return data;
  }

  async function scanPageContent(page, fetchImpl = fetch) {
    const validationMessage = validatePageContent(page);
    if (validationMessage) {
      throw new Error(validationMessage);
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(
      () => controller.abort(),
      REQUEST_TIMEOUT_MS,
    );

    try {
      const response = await fetchImpl(`${API_URL}/scan-page-content`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_url: page.url,
          page_title: page.title,
          page_text: page.text,
        }),
        signal: controller.signal,
      });
      return await readJsonResponse(response);
    } catch (error) {
      if (error?.name === "AbortError") {
        throw new Error(
          "The scan timed out while waiting for RecruitmentGuard. The server may be waking up; please try again.",
        );
      }
      if (error?.name === "TypeError") {
        throw new Error(
          "Could not connect to RecruitmentGuard. Check your internet connection and try again.",
        );
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  globalThis.RecruitmentGuardApi = Object.freeze({
    apiUrl: API_URL,
    requestTimeoutMs: REQUEST_TIMEOUT_MS,
    isSupportedPageUrl,
    readJsonResponse,
    scanPageContent,
    validatePageContent,
  });
})();
