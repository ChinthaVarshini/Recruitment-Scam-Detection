# RecruitmentGuard Job Checker

RecruitmentGuard Job Checker checks visible job-posting or offer-page text against the deployed RecruitmentGuard API.

## Install

### Chrome Web Store

After publication, install **RecruitmentGuard Job Checker** from its Chrome Web Store listing. Pin the extension from Chrome's Extensions menu for quick access.

### Test before publication

1. Download and extract `recruitmentguard-chrome-extension-v1.1.0.zip`.
2. Open `chrome://extensions`.
3. Turn on **Developer mode**.
4. Choose **Load unpacked** and select the extracted folder containing `manifest.json`.
5. Pin RecruitmentGuard from the Extensions menu.

## Use

1. Open a job-details page or offer page on a normal HTTP/HTTPS website.
2. Click the RecruitmentGuard toolbar icon.
3. Select **Check this job** and wait for the API assessment.
4. Review the risk score, model result, summary, and any matched warning signs. Use **Open RecruitmentGuard dashboard** for the full dashboard.

The extension reads up to 20,000 characters of visible page text after you click **Check this job**. It does not scan pages automatically, read browser history, or modify the page. Browser-internal pages, extension pages, and pages with no readable text cannot be scanned. For best results, open the individual job details or offer rather than a search-results list or inbox summary.

The API is hosted at `https://recruitment-scam-detection.onrender.com`. The first request after a period of inactivity can take longer while the service starts. A scan timeout, network failure, unsupported page, or API error is shown in the popup; retry after checking the page and your connection.

## Permissions

- `activeTab`: access the current tab only after the user invokes the extension.
- `scripting`: read visible text from that tab after the user selects **Check this job**.
- Production host access: send the scan request to the RecruitmentGuard API on Render.
- No job-site host access: `activeTab` grants temporary access only after the user opens the popup and starts a scan.

The extension does not request broad access to all websites. `activeTab` is used instead of persistent permissions for job sites.

## Privacy

When a user starts a scan, the extension sends the current page URL, page title, and up to 20,000 characters of visible page text to the RecruitmentGuard API over HTTPS. The backend processes that content to produce the assessment; the extension itself does not store or transmit scan history. The backend may store assessment metadata (job title, prediction, score, risk level, and a generated analysis ID) to support the feedback workflow, but the scan route does not save the full page text or source URL to that record. Optional feedback is submitted separately through the dashboard.

Review the [privacy-policy draft](PRIVACY_POLICY.md) and the project owner's published privacy policy before installing. The Web Store listing must link to the final, publicly accessible privacy policy.

## Troubleshooting

- **Cannot scan this page:** use a normal public HTTP/HTTPS job page, not `chrome://`, the Web Store, or another browser-internal page.
- **No readable text:** open the specific job details or offer message. The extension reads visible text only; it does not run OCR on page images.
- **Could not connect / timed out:** confirm internet access and try again. The hosted API may be waking after inactivity.
- **Unexpected or incomplete response:** retry later and report persistent issues using the support contact in the published Web Store listing.
- **The extension cannot be loaded:** extract the ZIP first and select the extracted folder whose top level contains `manifest.json`.

## Local API development

Production uses the hosted Render API by default. For local development only, change `API_URL` in `api.js` to `http://127.0.0.1:8000` and replace the production entry in `host_permissions` in `manifest.json` with `http://127.0.0.1:8000/*`, then reload the unpacked extension. Restore both production values before creating a release package.

## Chrome Web Store listing draft

- **Name:** RecruitmentGuard Job Checker
- **Short description:** Check visible job-posting text for recruitment scam warning signs before you apply.
- **Category:** Productivity
- **Detailed description:**

  Review a job posting before you apply with RecruitmentGuard Job Checker. Open the job details or offer page, click the extension, and choose **Check this job** to analyze up to 20,000 characters of visible page text.

  The extension sends the page URL, title, and visible text to the RecruitmentGuard API and displays the returned risk level, score, model result, summary, and matched warning signs. Open the RecruitmentGuard dashboard for the complete assessment.

  Scanning is user-initiated. The extension does not scan pages in the background, change the page, or access all websites. Results are decision support, not proof that a job is safe or fraudulent. Independently verify the employer and never pay recruitment fees.

- **Small icon:** `icons/icon16.png` / `icons/icon48.png` for extension UI; **Store listing icon:** `icons/icon128.png`.
- **Screenshots:** capture at least one current Chrome screenshot showing the extension popup with a real scan result; use Chrome Web Store accepted screenshot dimensions (at least 640 × 400). Add more screenshots for other real extension states if available. Do not submit mock scan results.
- **Privacy disclosures:** declare that user activity is collected only when the user explicitly starts a scan; the current page URL, title, and visible page text are transmitted to the RecruitmentGuard API for job-safety analysis. Link the final privacy policy. Do not claim that page text is never transmitted or that the backend retains no metadata.
- **Support contact:** configure a support email or support URL in the Web Store dashboard before submission.

## Package and validate

From the repository root in PowerShell:

```powershell
node --test extension/test/api.test.js
.\extension\package.ps1
```

The test command checks the production endpoint, request contract, unsupported/empty pages, genuine assessment handling, and friendly handling of network, non-JSON, API, and malformed-response errors. The packaging script validates referenced files and Manifest V3 configuration, then writes a ZIP containing only runtime extension files to `release/recruitmentguard-chrome-extension-v1.1.0.zip`. The ZIP has `manifest.json` at its root.
