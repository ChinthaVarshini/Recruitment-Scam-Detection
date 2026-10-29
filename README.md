# RecruitmentGuard

RecruitmentGuard is an explainable recruitment-scam detection system. It combines a TF-IDF machine-learning model with rule-based indicators, URL intelligence, multi-factor risk scoring, and safety recommendations.

## Project Interface

![RecruitmentGuard dashboard interface](screenshots/dashboard.png)

![RecruitmentGuard feedback analytics interface](screenshots/feedback-analytics.png)

![RecruitmentGuard risk assessment interface](screenshots/risk-assessment.png)

![RecruitmentGuard safety recommendations interface](screenshots/safety-recommendations.png)

![RecruitmentGuard browser extension](screenshots/browser-extension.png)

## Structure

- `data/`: raw, processed, and split datasets
- `notebooks/`: exploratory analysis and experiments
- `src/`: data, preprocessing, feature, model, evaluation, and explainability code
- `models/`: trained model artifacts
- `results/`: experiment outputs
- `backend/`: backend application
- `frontend/`: frontend application
- `extension/`: browser extension
- `tests/`: automated tests

## Run Locally

Create or activate a virtual environment, then install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start the API from the project root:

```powershell
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Start the dashboard in a second terminal:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```

Open `http://127.0.0.1:5174/`. The API is available at `http://127.0.0.1:8000/`, and interactive documentation is at `http://127.0.0.1:8000/docs`.

## API Contract

`GET /health` confirms that the trained model and vectorizer are loaded.

`POST /predict` accepts a JSON object with these optional text fields:

```json
{
	"title": "Software Engineer",
	"location": "Hyderabad / Remote",
	"company_profile": "Company information",
	"company_website": "https://company.com",
	"description": "Full job description",
	"requirements": "Skills and experience",
	"benefits": "Salary and benefits"
}
```

The response includes the model prediction, fraud probability, final risk score and level, explainable feature contributions, risk indicators, URL findings, employer-domain comparison, and safety recommendations. The optional `company_website` is compared with application-link domains; external links are informational and do not change the model risk score. The dashboard also accepts job-posting images and PDFs. Browser OCR extracts text from images and scanned PDFs, while text-based PDFs are read directly before analysis.

Hindi and Telugu text written in Devanagari/Telugu script is checked for a limited set of recruitment warning phrases, such as payment requests, urgency, and guaranteed earnings. Matching warning phrases are shown as evidence. The saved TF-IDF model was trained for English, so for detected Hindi/Telugu inputs it is deliberately not run: the response is `NEEDS_REVIEW`, the displayed risk score uses language-specific rule indicators only, and no ML fraud probability or model confidence is reported. Romanized Hindi/Telugu phrase matching is best-effort and does not replace a validated multilingual model. This language support is a prototype, not a comprehensive translation or scam detector.

For every rule-based warning indicator, the API returns the matched phrase in `evidence` and a short surrounding excerpt in `evidence_context`. The dashboard highlights the matched words, the browser extension lists the same warning evidence, and PDF assessment reports include each matched phrase. These are rule matches from the supplied text, not independent verification of the employer or claim.

After an assessment, select **Download PDF assessment report** to save a PDF containing the prediction, risk score, confidence, detected warning signs, URL findings when available, recommendations, and a decision-support disclaimer. PDF creation runs in the browser; no report content is uploaded for document generation.

## Job URL Scanner

Use **Scan a public job posting URL** in the dashboard to fetch a public job page, extract available JobPosting JSON-LD fields (with page-text fallback), fill the form, and run the existing risk assessment. Review the extracted fields and result before relying on them; pages that require login or block automated access may not scan successfully.

The API endpoint is `POST /scan-url` with `{"url":"https://public.example/jobs/role"}`. It returns `source_url`, `extracted_job`, and an `assessment` matching the regular `/predict` response.

For safety, the scanner allows only HTTP/HTTPS on standard ports, rejects private/local IPs and DNS answers, disables proxy environment settings, verifies the actual connected peer, blocks redirects to unsafe addresses, follows at most three redirects, accepts HTML only, and caps the downloaded response at 2 MB. DNS resolution has a five-second deadline, and page connections have connect/read timeouts. A DNS failure returns an explicit scan error; an unscanned URL is never assigned a low-risk result based on that failure, and DNS failure alone is not treated as evidence of fraud.

## Browser Extension

The Chromium extension provides a toolbar **Check this job** action for the active page. Start the RecruitmentGuard API, then open `chrome://extensions` (or `edge://extensions`), enable **Developer mode**, select **Load unpacked**, and choose the project's `extension/` folder. Open the job details page or offer email itself (not just the inbox list), click the extension icon, and choose **Check this job**. The popup shows the page title and risk assessment; use its dashboard link for the full report.

When you click **Check this job**, the extension reads up to 20,000 characters of visible text from the active tab and sends that text and its URL to the local API's `POST /scan-page-content` route. The route runs the existing assessment without making another request to the source website. The extension does not read page text until you click the button, does not modify the page, and sends the content only to the local API. The manifest grants temporary active-tab access and scripting permission, plus network permission only for the local API on port 8000. Open the specific job or offer message before scanning; inbox summaries and unrelated pages may not contain enough relevant text. Results are decision support, not a guarantee.

To test a known URL even if its website is offline, use **URL-only test mode (no website fetch)** in the dashboard, or call `POST /classify-url` with `{"urls":["https://example.com/jobs/role"]}`. This runs URL-feature extraction and the existing ML prediction on the URL text without resolving DNS or requesting the page. Its prediction is based only on the URL string, not on website contents or availability.

## Batch Job Analysis

In the dashboard, use **Batch job analysis** to upload a UTF-8 CSV and analyze up to 250 postings in one request (1 MB maximum). Download the provided template for the recommended column names. The API also accepts common aliases such as `Job Title`, `Company Name`, `Job Description`, and `combined_text`. Unknown fields are ignored; rows with missing content, overlong values, or malformed values are reported individually rather than treated as successful predictions.

The result summary shows analyzed, invalid, HIGH/CRITICAL, and duplicate counts. Pairwise duplicate checks flag identical normalized postings, highly similar text, and moderately similar text that shares multiple high-risk warning categories. Matches and similarity percentages are shown per row and can be exported. These are review cues, not proof that two listings share an author or are fraudulent. Export all analyzed rows, only high-risk rows, duplicate matches, or every row including validation errors. CSV cells are quoted and spreadsheet formula prefixes are neutralized in downloads. Batch predictions use the existing risk model and are decision support, not a guarantee; review postings and verify employers independently.

## Saved Scan History and Application Checklist

The dashboard saves up to 15 recent individual assessments and their job text in this browser's local storage so they can be reopened after a refresh. History can be cleared from the dashboard. It is stored on this browser only and is not synced to the API. Select two saved scans to compare their risk level, score, prediction, warning-sign count, and scan time.

The result panel includes a checklist for independently verifying the employer, recruiter email, application domain, payment requests, and sensitive information. Checklist progress is saved in this browser per job identity. Completing the checklist does not change a model score or guarantee legitimacy.

## Evaluation

Model evaluation scripts are in `src/evaluation/`. Run the automated checks with:

```powershell
pytest -q
```

For the focused URL scanner and API regression tests:

```powershell
pytest -q tests/test_job_page_scanner.py tests/test_job_url_api.py
```

The system is a decision-support tool. A low score does not guarantee that a job is safe, so users should verify the employer independently and never pay recruitment fees.

## Transformer Research Pipeline

The paper's main contribution is available as an optional training pipeline in `src/models/transformer_orf.py`. It supports both `bert-base-uncased` and `roberta-base`, mean-pools encoder embeddings, applies SMOTE in embedding space, trains a classifier, and reports accuracy, balanced accuracy, recall, sensitivity, specificity, F1-score, G-Mean, and a confusion matrix.

Install the additional transformer dependencies from the project root:

```powershell
pip install -r requirements.txt
```

Run both transformer comparisons:

```powershell
python src/models/transformer_orf.py --model both
```

For a comparison without oversampling:

```powershell
python src/models/transformer_orf.py --model both --no-smote
```

The first run downloads the pretrained models. Use a CUDA-enabled PyTorch installation and a GPU for practical training time; CPU execution is supported but slow. Outputs are saved under `artifacts/transformers/`. The implementation uses the project's available recruitment dataset, not the paper's combined Pakistan/US/Fake Job dataset, so its metrics must be reported as an extension rather than as a reproduction of the paper's numbers.

### Current Test Results

Evaluation was run on 2,647 held-out postings, including 128 fraudulent postings:

| Model | Accuracy | Fraud Recall | ROC-AUC | PR-AUC |
| --- | ---: | ---: | ---: | ---: |
| TF-IDF Logistic Regression | 98.04% | 86.72% | 0.9902 | 0.9134 |
| TF-IDF Linear SVM | 98.90% | 80.47% | 0.9895 | 0.9343 |
| Multi-Factor Logistic Regression | 97.58% | 87.50% | 0.9913 | 0.9127 |

On the same held-out test split, the multi-factor model has the highest fraud recall and ROC-AUC, while the SVM has the highest accuracy and PR-AUC. The split contains 2,647 postings (2,519 legitimate and 128 fraudulent); always present the class distribution because accuracy alone can hide missed fraud.

## Model Comparison Report

Compare the saved Logistic Regression, Linear SVM, and multi-factor models on the held-out test split:

```powershell
python -m src.evaluation.evaluate_models
```

The report includes fraud recall, precision, specificity, F1, G-Mean, ROC-AUC, PR-AUC, class counts, and the confusion matrix. JSON and CSV files are written to `results/evaluation/`. Models without saved artifacts are explicitly skipped. Keep the test split held out until final comparisons; do not use the report to tune model settings.

## Feedback Analytics and Controlled Model Improvement

Each supported prediction receives an analysis ID. Users can submit a suggested fraudulent/legitimate label and an optional explanation. The API stores the prediction label, fraud probability, final risk score, risk level, posting title, feedback label, explanation, timestamp, and review state in a local SQLite database at `data/feedback.sqlite3` by default; it does not store the full job posting. Existing databases receive a nullable `final_risk_score` column migration when opened. Feedback is pending until an authorized reviewer independently checks the posting and records the verified label. A repeat submission for the same assessment returns the original record rather than creating a duplicate.

The dashboard's Feedback Analytics section separates user-submitted labels from independently verified ground truth, and reports verified fraudulent, verified legitimate, pending, and rejected counts. Feedback-based precision, recall, F1-score, and the confusion matrix use only explicitly verified decisions and the original prediction captured for that assessment; metrics are shown only with at least 10 verified records and both ground-truth classes. The positive class is **Fraudulent**. These metrics are not held-out test-set metrics, and user submissions are not treated as confirmed errors.

Copy `.env.example` to `.env`, replace its placeholder admin key with a long random secret, and set it before starting the API. The key stays server-side; authorized reviewers enter it in the dashboard Reviewer Desk and it is held only in page memory.

```powershell
$env:RECRUITMENTGUARD_ADMIN_KEY = "use-a-long-random-secret"
$env:RECRUITMENTGUARD_REVIEWER_IDENTITY = "authorized-reviewer"
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Authorized reviewers can open **Reviewer Desk** and inspect pending items with their saved title, model prediction, risk score, user label, note, and submission time. Each review must choose `VERIFIED_FRAUDULENT`, `VERIFIED_LEGITIMATE`, or `REJECTED`; only the first two count as verified and are included in export. `GET /admin/feedback?review_status=PENDING` and `POST /admin/feedback/{id}/review` remain available to protected API clients. The API records `RECRUITMENTGUARD_REVIEWER_IDENTITY` and the review timestamp. Pending and rejected reports never contribute to evaluation metrics.

```powershell
$headers = @{ "X-Admin-Key" = $env:RECRUITMENTGUARD_ADMIN_KEY }
Invoke-RestMethod -Headers $headers "http://127.0.0.1:8000/admin/feedback?review_status=PENDING"
Invoke-RestMethod -Method Post -Headers $headers -ContentType "application/json" `
	-Body '{"decision":"VERIFIED_FRAUDULENT","review_note":"Employer and offer independently verified."}' `
	"http://127.0.0.1:8000/admin/feedback/1/review"
```

Export verified examples only with `GET /admin/feedback/export` and the same header. This is a label/prediction export for offline analysis; the full job text is not retained, so it is not a ready-made retraining dataset. No feedback submission retrains or replaces the production model. Preserve the original training data and model, evaluate any separately trained candidate on the existing held-out test set against the current baseline, and replace the production model only after it passes explicitly defined acceptance criteria.

## Docker Deployment

Docker Compose starts the API and dashboard, persists the feedback database, and checks API health before starting the frontend. Copy `.env.example` to `.env` and set a strong, private key:

```dotenv
RECRUITMENTGUARD_ADMIN_KEY=replace-with-a-long-random-secret
RECRUITMENTGUARD_REVIEWER_IDENTITY=authorized-reviewer
```

Then run:

```powershell
docker compose up --build
```

Open `http://127.0.0.1:8080/`; the API and interactive docs are available at `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/docs`. Keep `.env` private. This Compose setup is a deployment baseline, not a complete public-internet security configuration; use HTTPS, restrictive network access, and managed secrets before exposing it beyond a trusted environment.
