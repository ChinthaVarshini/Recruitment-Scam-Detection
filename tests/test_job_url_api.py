from fastapi.testclient import TestClient

from src.api import app as api_module
from src.api.app import app
from src.url_intelligence.job_page_scanner import JobPageScanError


def test_deployed_frontend_origin_is_allowed_for_api_preflight():
    with TestClient(app) as client:
        response = client.options(
            "/scan-page-content",
            headers={
                "Origin": "https://recruitment-scam-detection.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://recruitment-scam-detection.vercel.app"
    )
    assert response.headers["access-control-allow-methods"] == "GET, POST"


def test_unrecognized_origin_is_not_allowed_by_api_cors():
    with TestClient(app) as client:
        response = client.options(
            "/scan-page-content",
            headers={
                "Origin": "https://unrecognized.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_scan_url_extracts_job_and_runs_existing_assessment(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "scan_job_page",
        lambda _url: {
            "title": "Remote Data Entry",
            "location": "Hyderabad",
            "company_profile": "Acme Hiring",
            "company_website": "",
            "description": "Pay a registration fee immediately to apply.",
            "requirements": "No experience required",
            "benefits": "",
            "scanned_url": "https://jobs.example.test/role",
        },
    )

    with TestClient(app) as client:
        response = client.post(
            "/scan-url",
            json={"url": "https://jobs.example.test/role"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source_url"] == "https://jobs.example.test/role"
    assert body["extracted_job"]["title"] == "Remote Data Entry"
    assert body["assessment"]["analysis_id"]
    assert body["assessment"]["prediction"] in {"LEGITIMATE", "FRAUDULENT"}
    payment = next(
        item
        for item in body["assessment"]["risk_indicators"]
        if item["type"] == "PAYMENT_REQUEST"
    )
    assert payment["evidence"] == "registration fee"
    assert "registration fee" in payment["evidence_context"]


def test_scan_url_returns_safe_fetch_errors_as_client_errors(monkeypatch):
    def reject_private_url(_url):
        raise JobPageScanError("Local and private network addresses cannot be scanned.")

    monkeypatch.setattr(api_module, "scan_job_page", reject_private_url)

    with TestClient(app) as client:
        response = client.post(
            "/scan-url",
            json={"url": "http://127.0.0.1/private"},
        )

    assert response.status_code == 422
    assert "private network" in response.json()["detail"]["message"]
    assert response.json()["detail"]["code"] == "scan_failed"


def test_scan_url_reports_unresolved_hostname_without_prediction(monkeypatch):
    def unresolved(_url):
        raise JobPageScanError(
            "The hostname does not exist in DNS. Check the URL spelling or domain DNS records.",
            "hostname_unresolved",
        )

    monkeypatch.setattr(api_module, "scan_job_page", unresolved)

    with TestClient(app) as client:
        response = client.post(
            "/scan-url",
            json={"url": "https://missing.example.test/jobs"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "hostname_unresolved",
        "message": "The hostname does not exist in DNS. Check the URL spelling or domain DNS records.",
    }


def test_direct_url_classifier_uses_url_pipeline_without_fetching(monkeypatch):
    def unexpected_fetch(_url):
        raise AssertionError("URL-only classifier must not fetch website pages")

    monkeypatch.setattr(api_module, "scan_job_page", unexpected_fetch)

    with TestClient(app) as client:
        response = client.post(
            "/classify-url",
            json={"urls": ["https://urgent-payment.xyz/register"]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "url_only_no_fetch"
    assert body["urls"] == ["https://urgent-payment.xyz/register"]
    assessment = body["assessment"]
    assert assessment["url_test_mode"] is True
    assert assessment["url_intelligence"]["urls_detected"] == 1
    assert assessment["url_intelligence"]["urls"][0]["risk_level"] in {
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }
    assert assessment["prediction"] in {"LEGITIMATE", "FRAUDULENT"}
    assert "No DNS lookup or website fetch was performed" in assessment["url_test_notice"]


def test_visible_page_content_scan_uses_existing_assessment_without_fetch(monkeypatch):
    def unexpected_fetch(_url):
        raise AssertionError("Visible-content scan must not fetch the source URL")

    monkeypatch.setattr(api_module, "scan_job_page", unexpected_fetch)

    with TestClient(app) as client:
        response = client.post(
            "/scan-page-content",
            json={
                "source_url": "https://jobs.example.test/role",
                "page_title": "Remote Data Entry Job",
                "page_text": "Pay a registration fee immediately to apply. Contact the recruiter by WhatsApp.",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source_url"] == "https://jobs.example.test/role"
    assert body["page_title"] == "Remote Data Entry Job"
    assert body["assessment"]["analysis_id"]
    assert body["assessment"]["prediction"] in {"LEGITIMATE", "FRAUDULENT"}
    assert body["assessment"]["url_intelligence"]["urls_detected"] == 1
    assert any(
        item["type"] == "PAYMENT_REQUEST"
        for item in body["assessment"]["risk_indicators"]
    )


def test_visible_page_content_scan_rejects_invalid_source_or_empty_text():
    with TestClient(app) as client:
        invalid_source = client.post(
            "/scan-page-content",
            json={
                "source_url": "file:///C:/private.txt",
                "page_text": "Job opening",
            },
        )
        empty_text = client.post(
            "/scan-page-content",
            json={
                "source_url": "https://jobs.example.test/role",
                "page_text": "   ",
            },
        )

    assert invalid_source.status_code == 422
    assert empty_text.status_code == 422


def test_hindi_prediction_skips_english_model_and_reports_rule_only_result(monkeypatch):
    class ModelMustNotRun:
        def predict(self, _features):
            raise AssertionError("English model must not run for Hindi text")

        def predict_proba(self, _features):
            raise AssertionError("English model must not run for Hindi text")

    monkeypatch.setattr(api_module, "model", ModelMustNotRun())

    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "title": "ऑनलाइन नौकरी",
                "description": "नौकरी पाने के लिए पंजीकरण शुल्क जमा करें। सीमित पद हैं, अभी आवेदन करें।",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "hi"
    assert body["model_supported"] is False
    assert body["prediction"] == "NEEDS_REVIEW"
    assert body["fraud_probability"] is None
    assert body["scam_probability"] is None
    assert body["analysis_id"] is None
    assert body["risk_weights"] == {"ml_model": 0, "risk_indicators": 100}
    assert body["risk_level"] == "MEDIUM"
    assert any(item["type"] == "PAYMENT_REQUEST" for item in body["risk_indicators"])


def test_hindi_without_supported_warning_phrase_is_not_labeled_low_risk():
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "title": "सॉफ्टवेयर इंजीनियर",
                "description": "हमारी कंपनी में सॉफ्टवेयर इंजीनियर की नौकरी के लिए आवेदन करें।",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "hi"
    assert body["prediction"] == "NEEDS_REVIEW"
    assert body["risk_level"] == "NEEDS_REVIEW"
    assert body["final_risk_score"] is None
    assert "does not establish that the job is safe" in body["risk_summary"]["message"]


def test_telugu_content_is_assessed_using_rule_indicators_only(monkeypatch):
    class ModelMustNotRun:
        def predict(self, _features):
            raise AssertionError("English model must not run for Telugu text")

        def predict_proba(self, _features):
            raise AssertionError("English model must not run for Telugu text")

    monkeypatch.setattr(api_module, "model", ModelMustNotRun())

    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "title": "ఆన్‌లైన్ ఉద్యోగం",
                "description": "రిజిస్ట్రేషన్ ఫీజు చెల్లించండి. వెంటనే దరఖాస్తు చేయండి.",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "te"
    assert body["model_supported"] is False
    assert body["prediction"] == "NEEDS_REVIEW"
    assert body["fraud_probability"] is None
    assert {item["type"] for item in body["risk_indicators"]} >= {
        "PAYMENT_REQUEST",
        "URGENCY",
    }
