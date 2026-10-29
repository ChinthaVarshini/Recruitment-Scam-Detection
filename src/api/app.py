
import os
import sys
import joblib
import csv
import io
import secrets
import uuid
from urllib.parse import urlsplit

from typing import Literal, Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from starlette.concurrency import run_in_threadpool


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# IMPORTS
# ============================================================

from src.features.risk_indicators import detect_risk_indicators
from src.features.duplicate_jobs import find_duplicate_jobs
from src.features.multilingual_risk import (
    LANGUAGE_NAMES,
    detect_multilingual_risk_indicators,
)

from src.risk_engine.multi_factor_risk import (
    analyze_risk
)

from src.url_intelligence.url_analyzer import (
    analyze_urls
)
from src.url_intelligence.job_page_scanner import (
    JobPageScanError,
    scan_job_page,
)

from src.recommendation.recommendation_engine import (
    generate_recommendations
)
from src.api import feedback_store


# ============================================================
# MODEL PATHS
# ============================================================

MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "artifacts",
    "baseline",
    "logistic_regression_tfidf.joblib"
)

VECTORIZER_PATH = os.path.join(
    PROJECT_ROOT,
    "artifacts",
    "baseline",
    "tfidf_vectorizer.joblib"
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="RecruitmentGuard API",
    description=(
        "AI-powered recruitment scam detection using "
        "NLP, Machine Learning, URL Intelligence, "
        "Multi-Factor Risk Analysis and Safety Recommendations."
    ),
    version="3.0.0"
)


# ============================================================
# CORS
# ============================================================

cors_origins = (
    [
        origin.strip()
        for origin in os.getenv("RECRUITMENTGUARD_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if os.getenv("RECRUITMENTGUARD_CORS_ORIGINS")
    else [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
)
frontend_host = os.getenv("RECRUITMENTGUARD_FRONTEND_HOST", "").strip().rstrip("/")
if frontend_host:
    frontend_origin = (
        frontend_host
        if frontend_host.startswith(("http://", "https://"))
        else f"https://{frontend_host}"
    )
    if frontend_origin not in cors_origins:
        cors_origins.append(frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# LOAD TRAINED MODEL
# ============================================================

print("Loading trained model...")

try:

    model = joblib.load(
        MODEL_PATH
    )

    print("Model loaded successfully!")

except Exception as e:

    model = None

    print(
        "ERROR loading model:",
        e
    )


# ============================================================
# LOAD TF-IDF VECTORIZER
# ============================================================

print("Loading TF-IDF vectorizer...")

try:

    vectorizer = joblib.load(
        VECTORIZER_PATH
    )

    print(
        "Vectorizer loaded successfully!"
    )

except Exception as e:

    vectorizer = None

    print(
        "ERROR loading vectorizer:",
        e
    )


# ============================================================
# REQUEST SCHEMA
# ============================================================

class JobPosting(BaseModel):

    title: str = Field(default="", max_length=500)

    location: str = Field(default="", max_length=1000)

    company_profile: str = Field(default="", max_length=20000)

    company_website: str = Field(default="", max_length=2000)

    description: str = Field(default="", max_length=50000)

    requirements: str = Field(default="", max_length=20000)

    benefits: str = Field(default="", max_length=20000)


class FeedbackSubmission(BaseModel):
    prediction_id: str = Field(min_length=1, max_length=100)
    user_label: Literal["FRAUDULENT", "LEGITIMATE"]
    comment: str = Field(default="", max_length=1000)


class JobUrlScanRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class UrlClassifierRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=20)


class PageContentScanRequest(BaseModel):
    source_url: str = Field(min_length=1, max_length=2048)
    page_title: str = Field(default="", max_length=500)
    page_text: str = Field(min_length=1, max_length=50000)


MAX_BATCH_CSV_BYTES = 1_000_000
MAX_BATCH_ROWS = 250
BATCH_COLUMN_ALIASES = {
    "title": {"title", "job title", "job_title"},
    "location": {"location", "job location", "job_location"},
    "company_profile": {
        "company",
        "company name",
        "company_name",
        "company profile",
        "company_profile",
        "hiring organization",
    },
    "company_website": {
        "company website",
        "company_website",
        "company url",
        "website",
    },
    "description": {
        "description",
        "job description",
        "job_description",
        "job content",
        "job_content",
        "combined_text",
    },
    "requirements": {"requirements", "job requirements", "job_requirements"},
    "benefits": {"benefits", "job benefits", "job_benefits"},
}


class FeedbackReview(BaseModel):
    decision: Literal["VERIFIED_FRAUDULENT", "VERIFIED_LEGITIMATE", "REJECTED"]
    review_note: str = Field(default="", max_length=1000)


def require_admin_key(admin_key: str | None) -> None:
    configured_key = os.getenv("RECRUITMENTGUARD_ADMIN_KEY")
    if not configured_key:
        raise HTTPException(
            status_code=503,
            detail="Admin endpoints are disabled. Configure RECRUITMENTGUARD_ADMIN_KEY.",
        )
    if not admin_key or not secrets.compare_digest(admin_key, configured_key):
        raise HTTPException(status_code=401, detail="A valid X-Admin-Key is required.")


def _canonical_batch_header(header: str) -> str | None:
    normalized = " ".join(header.strip().lower().replace("-", " ").split())
    for field, aliases in BATCH_COLUMN_ALIASES.items():
        if normalized in aliases:
            return field
    return None


def _batch_result(row_number: int, job_values: dict[str, str]) -> dict[str, Any]:
    title = job_values.get("title", "").strip() or "Untitled job posting"
    try:
        job = JobPosting(**job_values)
    except ValidationError as error:
        return {
            "row_number": row_number,
            "title": title,
            "status": "INVALID",
            "error": "; ".join(
                f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
                for issue in error.errors()
            ),
        }
    try:
        assessment = predict_job(job)
    except HTTPException as error:
        if error.status_code == 400:
            return {
                "row_number": row_number,
                "title": title,
                "status": "INVALID",
                "error": error.detail,
            }
        raise
    return {
        "row_number": row_number,
        "title": title,
        "company": job.company_profile.strip(),
        "location": job.location.strip(),
        "status": "ANALYZED",
        "analysis_id": assessment["analysis_id"],
        "prediction": assessment["prediction"],
        "final_risk_score": assessment["final_risk_score"],
        "risk_level": assessment["risk_level"],
        "fraud_probability": assessment["fraud_probability"],
        "scam_probability": assessment["scam_probability"],
        "risk_indicators": assessment["risk_indicators"],
        "fraud_reasons": assessment["fraud_reasons"][:5],
        "_duplicate_text": " ".join(
            (
                job.title,
                job.company_profile,
                job.location,
                job.description,
                job.requirements,
                job.benefits,
            )
        ),
    }


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
def root():

    return {

        "message": "RecruitmentGuard API",

        "status": "running",

        "version": "3.0.0",

        "model_loaded": model is not None,

        "vectorizer_loaded": vectorizer is not None,

        "features": [

            "TF-IDF NLP",

            "Logistic Regression",

            "Explainable AI",

            "Risk Indicators",

            "Multi-Factor Risk Engine",

            "URL Intelligence",

            "Public Job URL Scanner",

            "Safety Recommendations",

            "Confidence Score"
        ]
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    if model is None or vectorizer is None:

        return {

            "status": "unhealthy",

            "model_loaded": model is not None,

            "vectorizer_loaded": vectorizer is not None,

            "risk_engine": "Multi-Factor Risk Engine",

            "url_intelligence": "URL Intelligence Engine",

            "recommendation_engine": "Recommendation Engine"
        }

    return {

        "status": "healthy",

        "model": "TF-IDF Logistic Regression",

        "model_loaded": True,

        "vectorizer_loaded": True,

        "risk_engine": "Multi-Factor Risk Engine",

        "url_intelligence": "URL Intelligence Engine",

        "recommendation_engine": "Recommendation Engine"
    }


@app.post("/feedback", status_code=201)
def submit_feedback(submission: FeedbackSubmission):
    feedback = feedback_store.create_feedback(
        prediction_id=submission.prediction_id,
        user_label=submission.user_label,
        comment=submission.comment.strip(),
    )
    if feedback is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis was not found. Submit feedback for a result from this API.",
        )
    already_submitted = feedback["already_submitted"]
    return {
        "message": (
            "Feedback was already recorded for this assessment."
            if already_submitted
            else "Feedback submitted successfully. Your report is pending verification."
        ),
        "feedback_id": feedback["id"],
        "already_submitted": already_submitted,
    }


@app.get("/feedback/analytics")
def feedback_analytics():
    return feedback_store.get_analytics()


@app.get("/admin/feedback/summary")
def feedback_summary(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    require_admin_key(x_admin_key)
    return feedback_store.get_summary()


@app.get("/admin/feedback")
def list_submitted_feedback(
    review_status: Literal["PENDING", "REVIEWED"] | None = Query(default=None),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
):
    require_admin_key(x_admin_key)
    return {"feedback": feedback_store.list_feedback(review_status)}


@app.post("/admin/feedback/{feedback_id}/review")
def review_submitted_feedback(
    feedback_id: int,
    review: FeedbackReview,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
):
    require_admin_key(x_admin_key)
    reviewed = feedback_store.review_feedback(
        feedback_id,
        decision=review.decision,
        review_note=review.review_note.strip(),
        reviewer_identity=(
            os.getenv("RECRUITMENTGUARD_REVIEWER_IDENTITY", "authorized-reviewer").strip()
            or "authorized-reviewer"
        )[:100],
    )
    if reviewed is None:
        raise HTTPException(status_code=404, detail="Pending feedback record was not found.")
    return {"message": "Review decision recorded.", "feedback": reviewed}


@app.get("/admin/feedback/export")
def export_feedback(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
):
    require_admin_key(x_admin_key)
    records = feedback_store.list_verified_feedback()
    output = io.StringIO()
    fieldnames = [
        "id",
        "prediction_id",
        "title",
        "model_prediction",
        "fraud_probability",
        "risk_level",
        "final_risk_score",
        "user_label",
        "comment",
        "submitted_at",
        "review_status",
        "review_label",
        "review_decision",
        "reviewer_identity",
        "review_note",
        "reviewed_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="recruitmentguard-feedback.csv"'},
    )


@app.post("/batch-predict")
async def batch_predict(request: Request):
    if model is None or vectorizer is None:
        raise HTTPException(status_code=503, detail="The prediction model is unavailable.")
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"text/csv", "application/csv"}:
        raise HTTPException(status_code=415, detail="Upload CSV data using Content-Type: text/csv.")

    declared_length = request.headers.get("content-length")
    if declared_length:
        try:
            if int(declared_length) > MAX_BATCH_CSV_BYTES:
                raise HTTPException(status_code=413, detail="CSV file exceeds the 1 MB limit.")
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from error

    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > MAX_BATCH_CSV_BYTES:
            raise HTTPException(status_code=413, detail="CSV file exceeds the 1 MB limit.")
        chunks.append(chunk)
    try:
        csv_text = b"".join(chunks).decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="CSV must be encoded as UTF-8.") from error

    reader = csv.DictReader(io.StringIO(csv_text, newline=""), strict=True)
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV must include a header row.")

    mapped_headers = [
        (header, _canonical_batch_header(header))
        for header in reader.fieldnames
        if header is not None
    ]
    usable_headers = [(header, field) for header, field in mapped_headers if field]
    canonical_fields = [field for _, field in usable_headers]
    if not usable_headers:
        expected = ", ".join(sorted(BATCH_COLUMN_ALIASES))
        raise HTTPException(
            status_code=422,
            detail=f"CSV needs at least one recognized job field. Expected columns include: {expected}.",
        )
    if len(canonical_fields) != len(set(canonical_fields)):
        raise HTTPException(
            status_code=422,
            detail="CSV has duplicate columns that map to the same job field.",
        )

    results: list[dict[str, Any]] = []
    try:
        for row in reader:
            row_number = reader.line_num
            if len(results) >= MAX_BATCH_ROWS:
                raise HTTPException(
                    status_code=413,
                    detail=f"CSV exceeds the {MAX_BATCH_ROWS}-job limit.",
                )
            if None in row:
                results.append({
                    "row_number": row_number,
                    "title": "Invalid CSV row",
                    "status": "INVALID",
                    "error": "Row contains more values than the header.",
                })
                continue
            job_values = {
                field: (row.get(header) or "").strip()
                for header, field in usable_headers
            }
            if not any(job_values.values()):
                results.append({
                    "row_number": row_number,
                    "title": "Blank row",
                    "status": "INVALID",
                    "error": "Row does not contain any job details.",
                })
                continue
            results.append(await run_in_threadpool(_batch_result, row_number, job_values))
    except csv.Error as error:
        raise HTTPException(status_code=422, detail=f"Malformed CSV near line {reader.line_num}: {error}") from error

    duplicate_pairs, duplicate_rows = find_duplicate_jobs(results)
    analyzed = sum(result["status"] == "ANALYZED" for result in results)
    high_risk = sum(
        result.get("risk_level") in {"HIGH", "CRITICAL"}
        for result in results
        if result["status"] == "ANALYZED"
    )
    return {
        "total_rows": len(results),
        "analyzed_count": analyzed,
        "invalid_count": len(results) - analyzed,
        "high_risk_count": high_risk,
        "duplicate_pair_count": duplicate_pairs,
        "duplicate_row_count": duplicate_rows,
        "results": results,
    }


# ============================================================
# PREDICTION ENDPOINT
# ============================================================

@app.post("/scan-url")
def scan_job_url(request: JobUrlScanRequest):
    if model is None or vectorizer is None:
        raise HTTPException(status_code=503, detail="The prediction model is unavailable.")
    try:
        extracted_job = scan_job_page(request.url)
    except JobPageScanError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "message": str(error)},
        ) from error

    assessment = predict_job(JobPosting(**{
        key: value
        for key, value in extracted_job.items()
        if key != "scanned_url"
    }))
    return {
        "source_url": extracted_job["scanned_url"],
        "extracted_job": extracted_job,
        "assessment": assessment,
    }


@app.post("/classify-url")
def classify_url_text(request: UrlClassifierRequest):
    if model is None or vectorizer is None:
        raise HTTPException(status_code=503, detail="The prediction model is unavailable.")

    urls = [url.strip() for url in request.urls]
    if any(not url or len(url) > 2048 for url in urls):
        raise HTTPException(
            status_code=422,
            detail="Each URL must contain between 1 and 2048 characters.",
        )

    for url in urls:
        try:
            parsed = urlsplit(url)
            parsed.port
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid URL: {url}",
            ) from error
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise HTTPException(
                status_code=422,
                detail="Enter complete HTTP or HTTPS URLs without embedded credentials.",
            )

    assessment = predict_job(
        JobPosting(
            title="URL-only test (no website fetch)",
            description="\n".join(urls),
        )
    )
    assessment["url_test_mode"] = True
    assessment["url_test_notice"] = (
        "This prediction uses the URL text only. No DNS lookup or website fetch was performed; "
        "site availability is not evidence of fraud."
    )
    return {
        "mode": "url_only_no_fetch",
        "urls": urls,
        "assessment": assessment,
    }


@app.post("/scan-page-content")
def scan_visible_page_content(request: PageContentScanRequest):
    source_url = request.source_url.strip()
    page_text = request.page_text.strip()
    if not page_text:
        raise HTTPException(
            status_code=422,
            detail="No readable page text was provided. Open the job details and try again.",
        )
    try:
        parsed_source = urlsplit(source_url)
        parsed_source.port
    except ValueError as error:
        raise HTTPException(status_code=422, detail="The page URL is malformed.") from error
    if (
        parsed_source.scheme.lower() not in {"http", "https"}
        or not parsed_source.hostname
        or parsed_source.username
        or parsed_source.password
    ):
        raise HTTPException(
            status_code=422,
            detail="The source URL must be a valid HTTP or HTTPS page URL.",
        )

    assessment = predict_job(
        JobPosting(
            title=request.page_title.strip() or "Visible page content",
            description=f"{page_text}\n{source_url}",
        )
    )
    return {
        "source_url": source_url,
        "page_title": request.page_title.strip(),
        "assessment": assessment,
    }


@app.post("/predict")
def predict_job(job: JobPosting):

    # ========================================================
    # CHECK MODEL
    # ========================================================

    if model is None:

        raise HTTPException(
            status_code=500,
            detail="ML model could not be loaded."
        )

    if vectorizer is None:

        raise HTTPException(
            status_code=500,
            detail="TF-IDF vectorizer could not be loaded."
        )


    # ========================================================
    # COMBINE JOB INFORMATION
    # ========================================================

    combined_text = " ".join(
        [
            job.title,
            job.location,
            job.company_profile,
            job.description,
            job.requirements,
            job.benefits
        ]
    ).strip()


    # ========================================================
    # EMPTY INPUT CHECK
    # ========================================================

    if not combined_text:

        raise HTTPException(
            status_code=400,
            detail="Job posting cannot be empty."
        )


    # ========================================================
    # TF-IDF TRANSFORMATION
    # ========================================================

    X = vectorizer.transform(
        [combined_text]
    )


    # ========================================================
    # ML PREDICTION
    # ========================================================

    language, multilingual_indicators = detect_multilingual_risk_indicators(
        combined_text
    )
    model_supported = language not in {"hi", "te"}

    if model_supported:
        prediction = int(model.predict(X)[0])
        fraud_probability = float(model.predict_proba(X)[0][1])
        scam_probability = round(fraud_probability * 100, 2)
    else:
        prediction = None
        fraud_probability = None
        scam_probability = None


    # ========================================================
    # EXPLAINABLE AI
    # ========================================================

    contributions = []
    if model_supported:
        feature_names = vectorizer.get_feature_names_out()
        coefficients = model.coef_[0]
        feature_indices = X.nonzero()[1]
        for idx in feature_indices:
            tfidf_value = X[0, idx]
            contribution = tfidf_value * coefficients[idx]
            contributions.append(
                {
                    "feature": feature_names[idx],
                    "contribution": round(float(contribution), 6),
                }
            )


    # ========================================================
    # FRAUD FEATURES
    # ========================================================

    fraud_reasons = sorted(
        [
            item
            for item in contributions
            if item["contribution"] > 0
        ],
        key=lambda x: x["contribution"],
        reverse=True
    )[:10]


    # ========================================================
    # LEGITIMATE FEATURES
    # ========================================================

    legitimate_reasons = sorted(
        [
            item
            for item in contributions
            if item["contribution"] < 0
        ],
        key=lambda x: x["contribution"]
    )[:10]


    # ========================================================
    # RULE-BASED RISK INDICATORS
    # ========================================================

    risk_indicators = detect_risk_indicators(
        combined_text
    )
    existing_indicator_types = {item["type"] for item in risk_indicators}
    risk_indicators.extend(
        indicator
        for indicator in multilingual_indicators
        if indicator["type"] not in existing_indicator_types
    )


    # ========================================================
    # MULTI-FACTOR RISK ENGINE
    # ========================================================

    multi_factor_result = analyze_risk(
        ml_probability=fraud_probability if model_supported else 0.5,
        risk_indicators=risk_indicators,
        ml_supported=model_supported,
    )


    # ========================================================
    # URL INTELLIGENCE
    # ========================================================

    url_intelligence = analyze_urls(
        combined_text,
        official_website=job.company_website
    )


    # ========================================================
    # RECOMMENDATION ENGINE
    # ========================================================

    recommendation_result = generate_recommendations(

        risk_indicators=risk_indicators,

        url_intelligence=url_intelligence,

        final_risk_score=multi_factor_result[
            "final_risk_score"
        ],

        risk_level=multi_factor_result[
            "risk_level"
        ]
    )
    needs_language_review = not model_supported and not multilingual_indicators
    final_risk_score = (
        None
        if needs_language_review
        else multi_factor_result["final_risk_score"]
    )
    final_risk_level = (
        "NEEDS_REVIEW"
        if needs_language_review
        else multi_factor_result["risk_level"]
    )
    final_risk_color = (
        "GRAY"
        if needs_language_review
        else multi_factor_result["risk_color"]
    )
    risk_summary = multi_factor_result["summary"]
    overall_advice = recommendation_result["overall_advice"]
    if needs_language_review:
        risk_summary = {
            **risk_summary,
            "message": (
                "No supported Hindi/Telugu warning phrase was detected. "
                "This does not establish that the job is safe; verify the employer independently."
            ),
        }
        overall_advice = (
            "This Hindi/Telugu scan found no supported warning phrase. "
            "That is not proof the job is safe. Verify the employer independently."
        )


    # ========================================================
    # PREDICTION LABEL
    # ========================================================

    if not model_supported:
        prediction_label = "NEEDS_REVIEW"
    elif prediction == 1:

        prediction_label = "FRAUDULENT"

    else:

        prediction_label = "LEGITIMATE"

    analysis_id = str(uuid.uuid4()) if model_supported else None
    if analysis_id is not None:
        feedback_store.create_analysis(
            prediction_id=analysis_id,
            title=job.title.strip() or "Untitled job posting",
            model_prediction=prediction_label,
            fraud_probability=fraud_probability,
            risk_level=final_risk_level,
            final_risk_score=final_risk_score,
        )


    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return {

        "analysis_id": analysis_id,

        # ----------------------------------------------------
        # PREDICTION
        # ----------------------------------------------------

        "prediction": prediction_label,

        "fraud_probability": round(
            fraud_probability,
            4
        ) if fraud_probability is not None else None,

        "scam_probability": scam_probability,


        # ----------------------------------------------------
        # MULTI-FACTOR RISK
        # ----------------------------------------------------

        "ml_score": multi_factor_result[
            "ml_score"
        ],

        "indicator_score": multi_factor_result[
            "indicator_score"
        ],

        "final_risk_score": final_risk_score,

        "risk_level": final_risk_level,

        "risk_color": final_risk_color,

        "confidence": None if not model_supported else multi_factor_result["confidence"],


        # ----------------------------------------------------
        # RISK WEIGHTS
        # ----------------------------------------------------

        "risk_weights": multi_factor_result[
            "weights"
        ],


        # ----------------------------------------------------
        # EXPLAINABLE AI
        # ----------------------------------------------------

        "fraud_reasons": fraud_reasons,

        "legitimate_reasons": legitimate_reasons,


        # ----------------------------------------------------
        # RISK INDICATORS
        # ----------------------------------------------------

        "risk_indicators": risk_indicators,

        "language": language,

        "language_name": LANGUAGE_NAMES.get(language, LANGUAGE_NAMES["unknown"]),

        "model_supported": model_supported,

        "model_language_notice": (
            None
            if model_supported
            else (
                "The English-trained ML model was not used for this Hindi/Telugu text. "
                "The risk score uses matching language-specific warning signs only. "
                "A result of NEEDS_REVIEW is not a fraud verdict."
            )
        ),


        # ----------------------------------------------------
        # URL INTELLIGENCE
        # ----------------------------------------------------

        "url_intelligence": url_intelligence,


        # ----------------------------------------------------
        # SAFETY RECOMMENDATIONS
        # ----------------------------------------------------

        "recommendations": recommendation_result[
            "recommendations"
        ],

        "overall_advice": overall_advice,

        "recommendation_count": recommendation_result[
            "recommendation_count"
        ],


        # ----------------------------------------------------
        # RISK SUMMARY
        # ----------------------------------------------------

        "risk_summary": risk_summary,


        # ----------------------------------------------------
        # INPUT INFORMATION
        # ----------------------------------------------------

        "input": {

            "title": job.title,

            "location": job.location
        }
    }
