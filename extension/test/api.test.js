import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { runInNewContext } from "node:vm";
import test from "node:test";

const source = await readFile(new URL("../api.js", import.meta.url), "utf8");

function createApi() {
  const context = {
    AbortController,
    clearTimeout,
    fetch,
    globalThis: {},
    setTimeout,
    URL,
  };
  runInNewContext(source, context);
  return context.globalThis.RecruitmentGuardApi;
}

function assessmentResponse(overrides = {}) {
  return new Response(
    JSON.stringify({
      assessment: {
        risk_level: "LOW",
        final_risk_score: 16,
        risk_indicators: [],
        ...overrides,
      },
    }),
    { headers: { "content-type": "application/json" } },
  );
}

test("production API is the deployed Render service", () => {
  const api = createApi();
  assert.equal(api.apiUrl, "https://recruitment-scam-detection.onrender.com");
  assert.equal(api.requestTimeoutMs, 90000);
});

test("only HTTP and HTTPS tabs can be scanned", () => {
  const api = createApi();
  assert.equal(api.isSupportedPageUrl("https://jobs.example.test/role"), true);
  assert.equal(api.isSupportedPageUrl("http://jobs.example.test/role"), true);
  assert.equal(api.isSupportedPageUrl("chrome://extensions"), false);
  assert.equal(api.isSupportedPageUrl("not a URL"), false);
});

test("empty or unsupported page content is rejected before sending a request", () => {
  const api = createApi();
  assert.match(
    api.validatePageContent({ url: "https://jobs.example.test", text: "  " }),
    /No readable page text/,
  );
  assert.match(
    api.validatePageContent({ url: "chrome://extensions", text: "Extensions" }),
    /public HTTP or HTTPS/,
  );
  assert.equal(
    api.validatePageContent({ url: "https://jobs.example.test", text: "Job details" }),
    "",
  );
});

test("scan sends the expected POST request and returns actual JSON assessment", async () => {
  const api = createApi();
  const page = {
    url: "https://jobs.example.test/role",
    title: "Customer support role",
    text: "Visible job description",
  };
  let requestUrl;
  let requestOptions;

  const result = await api.scanPageContent(page, async (url, options) => {
    requestUrl = url;
    requestOptions = options;
    return assessmentResponse({ prediction: "LEGITIMATE" });
  });

  assert.equal(
    requestUrl,
    "https://recruitment-scam-detection.onrender.com/scan-page-content",
  );
  assert.equal(requestOptions.method, "POST");
  assert.equal(requestOptions.headers["Content-Type"], "application/json");
  assert.equal(JSON.stringify(JSON.parse(requestOptions.body)), JSON.stringify({
    source_url: page.url,
    page_title: page.title,
    page_text: page.text,
  }));
  assert.equal(result.assessment.prediction, "LEGITIMATE");
});

test("network errors are reported in user-friendly language", async () => {
  const api = createApi();
  await assert.rejects(
    api.scanPageContent(
      { url: "https://jobs.example.test", title: "Role", text: "Job details" },
      async () => {
        throw new TypeError("fetch failed");
      },
    ),
    /Could not connect to RecruitmentGuard/,
  );
});

test("non-JSON backend errors include status and response details", async () => {
  const api = createApi();
  await assert.rejects(
    api.readJsonResponse(
      new Response("The service is waking up", {
        status: 503,
        headers: { "content-type": "text/plain" },
      }),
    ),
    /HTTP 503.*text\/plain.*The service is waking up/,
  );
});

test("backend JSON errors display their detail message", async () => {
  const api = createApi();
  await assert.rejects(
    api.readJsonResponse(
      new Response('{"detail":"No readable page text was provided."}', {
        status: 422,
        headers: { "content-type": "application/json" },
      }),
    ),
    /No readable page text was provided/,
  );
});

test("invalid assessment payloads are rejected", async () => {
  const api = createApi();
  await assert.rejects(
    api.readJsonResponse(
      new Response('{"assessment":{"risk_level":"LOW"}}', {
        headers: { "content-type": "application/json" },
      }),
    ),
    /incomplete scan results/,
  );
  await assert.rejects(
    api.readJsonResponse(
      new Response('{"assessment":null}', {
        headers: { "content-type": "application/json" },
      }),
    ),
    /incomplete scan results/,
  );
});

test("malformed JSON responses are reported without crashing", async () => {
  const api = createApi();
  await assert.rejects(
    api.readJsonResponse(
      new Response("{not json", {
        headers: { "content-type": "application/json" },
      }),
    ),
    /invalid response/,
  );
});
