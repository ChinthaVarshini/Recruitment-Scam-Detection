# RecruitmentGuard Job Checker Privacy Policy (Draft)

**Status:** Draft for owner review. Publish this policy at a stable public HTTPS URL and replace the bracketed contact placeholder before submitting the extension to the Chrome Web Store.

**Effective date:** [Set publication date]
**Publisher:** [Add publisher or organization name]
**Privacy/support contact:** [Add a monitored email address or support URL]

## Information processed

When you click **Check this job**, RecruitmentGuard Job Checker reads the active tab's URL, page title, and up to 20,000 characters of visible page text. It sends these values over HTTPS to `https://recruitment-scam-detection.onrender.com` to generate a job-post assessment. The extension does not read page content until you start a scan.

The extension does not itself save scan history, page text, or browsing history. The backend's scan route uses the submitted text to calculate the assessment and does not store the full page text or source URL in the analysis record. For supported English-model assessments, the backend creates an analysis record containing a generated analysis ID, job title, model prediction, fraud probability, risk level, final risk score, and timestamp. This metadata supports the optional feedback workflow. The backend's storage and retention depend on the service's configured database and deployment.

If you separately choose to submit feedback through the dashboard, the backend stores the feedback label, optional comment, associated assessment metadata, submission time, and review status. Feedback is not submitted by the browser extension itself.

## Purpose and sharing

Submitted page content is processed to return the requested assessment. It is sent to the RecruitmentGuard backend hosted by Render. The extension does not sell page content or send it to the job site. The backend host may process routine connection or service logs according to its hosting configuration and policies. This draft does not assert a log-retention period that has not been independently established.

## User controls

Scanning is optional and user-initiated. Close the popup or do not click **Check this job** to avoid submitting page content. You can avoid submitting information by not using the extension on pages containing sensitive or personal material.

## Security and retention

Requests to the production API use HTTPS. The extension requests active-tab access for the current page and host access to the RecruitmentGuard API; it does not require persistent access to all websites. Assessment metadata and optional feedback are retained in the backend's configured database. The extension publisher should document retention and deletion procedures here after confirming the deployed database and operational policy.

## Children's privacy

RecruitmentGuard Job Checker is not designed for children and does not knowingly collect information from children.

## Changes and contact

This policy may be updated when the extension or backend data handling changes. For questions or privacy requests, contact: [Add a monitored email address or support URL].
