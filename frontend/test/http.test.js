import assert from "node:assert/strict";
import test from "node:test";

import { readJsonResponse, resolveApiUrl } from "../src/http.js";

test("production defaults to the deployed RecruitmentGuard API", () => {
  assert.equal(
    resolveApiUrl(undefined, true),
    "https://recruitment-scam-detection.onrender.com",
  );
});

test("development defaults to the same-origin API proxy", () => {
  assert.equal(resolveApiUrl(undefined, false), "/api");
});

test("relative API paths stay relative and are not converted to malformed URLs", () => {
  assert.equal(resolveApiUrl("/api/", true), "/api");
});

test("host-only API settings are normalized to HTTPS", () => {
  assert.equal(
    resolveApiUrl("recruitment-scam-detection.onrender.com/", true),
    "https://recruitment-scam-detection.onrender.com",
  );
});

test("explicit API URLs lose trailing slashes", () => {
  assert.equal(
    resolveApiUrl("https://api.example.test///", true),
    "https://api.example.test",
  );
});

test("JSON responses are parsed and returned", async () => {
  const response = new Response('{"total_submissions":0}', {
    headers: { "content-type": "application/json" },
  });

  assert.deepEqual(await readJsonResponse(response, "Analytics failed."), {
    total_submissions: 0,
  });
});

test("text and HTML errors report status and response content without JSON parsing", async () => {
  const response = new Response("The page could not be found", {
    status: 404,
    headers: { "content-type": "text/plain; charset=utf-8" },
  });

  await assert.rejects(
    readJsonResponse(response, "Could not load feedback analytics."),
    /HTTP 404.*text\/plain.*The page could not be found/,
  );
});

test("JSON API errors use the backend detail message", async () => {
  const response = new Response('{"detail":"Database unavailable"}', {
    status: 503,
    headers: { "content-type": "application/json" },
  });

  await assert.rejects(
    readJsonResponse(response, "Could not load feedback analytics."),
    /Database unavailable/,
  );
});

test("malformed JSON responses show a readable error", async () => {
  const response = new Response("{invalid", {
    headers: { "content-type": "application/json" },
  });

  await assert.rejects(
    readJsonResponse(response, "Could not load feedback analytics."),
    /server returned invalid JSON/,
  );
});
