export const PRODUCTION_API_URL =
  "https://recruitment-scam-detection.onrender.com";

export function resolveApiUrl(configuredApiUrl, isProduction) {
  const apiUrl = configuredApiUrl?.trim();
  if (!apiUrl) {
    return isProduction ? PRODUCTION_API_URL : "/api";
  }

  if (apiUrl.startsWith("/")) {
    return apiUrl.replace(/\/+$/, "") || "/";
  }

  return /^https?:\/\//i.test(apiUrl)
    ? apiUrl.replace(/\/+$/, "")
    : `https://${apiUrl.replace(/\/+$/, "")}`;
}

export async function readJsonResponse(response, fallbackMessage) {
  const contentType = response.headers.get("content-type") || "";
  const isJson =
    /application\/json/i.test(contentType) || /\+json/i.test(contentType);

  if (!isJson) {
    const body = (await response.text()).trim().replace(/\s+/g, " ");
    const details = body ? ` Response: ${body.slice(0, 180)}` : "";
    throw new Error(
      `${fallbackMessage} (HTTP ${response.status}): expected a JSON response, but received ${contentType || "an unknown content type"}.${details}`,
    );
  }

  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      `${fallbackMessage} (HTTP ${response.status}): the server returned invalid JSON.`,
    );
  }

  if (!response.ok) {
    throw new Error(data.detail || data.message || `${fallbackMessage} (HTTP ${response.status}).`);
  }

  return data;
}
