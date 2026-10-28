# RecruitmentGuard Dashboard

The React/Vite dashboard provides job-post analysis, explainable risk results, image/PDF text extraction, user feedback, feedback analytics, and the key-gated Reviewer Desk.

## Local development

From the project root, start the FastAPI API as described in the root [README](../README.md). Then run:

```powershell
npm ci
npm run dev -- --host 127.0.0.1 --port 5174
```

During local development, Vite proxies `/api` requests to `http://127.0.0.1:8000`, avoiding browser CORS errors if Vite selects a different port because the default is occupied. Set `VITE_API_URL` at build time to use another API base URL.

## Checks

```powershell
npm run lint
npm run build
```

The root Docker Compose setup builds this dashboard for Nginx and proxies `/api/` requests to the API service.
