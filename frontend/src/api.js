import { resolveApiUrl } from "./http.js";

export const API_URL = resolveApiUrl(
  import.meta.env.VITE_API_URL,
  import.meta.env.PROD,
);
