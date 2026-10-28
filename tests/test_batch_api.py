from fastapi.testclient import TestClient

from src.api import app as api_module
from src.api.app import MAX_BATCH_ROWS, app


def _assessment(job):
    return {
        "analysis_id": "test-analysis",
        "prediction": "FRAUDULENT",
        "final_risk_score": 87.5,
        "risk_level": "HIGH",
        "fraud_probability": 0.9,
        "scam_probability": 90.0,
        "risk_indicators": [{"type": "PAYMENT_REQUEST", "severity": "CRITICAL"}],
        "fraud_reasons": [{"feature": "registration fee"}],
    }


def test_batch_analysis_accepts_aliases_and_reports_invalid_rows(monkeypatch):
    monkeypatch.setattr(api_module, "predict_job", _assessment)
    content = (
        "Job Title,Company Name,Job Description,Location\n"
        '"Data Analyst","Example Ltd","Build reporting tools","Hyderabad"\n'
        ',,,\n'
        '"Scam Role","Bad Company","Pay a registration fee","Remote"\n'
        f'{"X" * 501},,,\n'
    )

    with TestClient(app) as client:
        response = client.post(
            "/batch-predict",
            content=content.encode("utf-8"),
            headers={"Content-Type": "text/csv"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 4
    assert body["analyzed_count"] == 2
    assert body["invalid_count"] == 2
    assert body["high_risk_count"] == 2
    assert body["results"][0]["title"] == "Data Analyst"
    assert body["results"][0]["location"] == "Hyderabad"
    assert body["results"][1]["status"] == "INVALID"
    assert body["results"][1]["error"] == "Row does not contain any job details."
    assert body["results"][3]["status"] == "INVALID"
    assert "title" in body["results"][3]["error"]


def test_batch_upload_rejects_unknown_headers_and_wrong_content_type():
    with TestClient(app) as client:
        unknown = client.post(
            "/batch-predict",
            content=b"foo,bar\n1,2\n",
            headers={"Content-Type": "text/csv"},
        )
        wrong_type = client.post(
            "/batch-predict",
            content=b"title,description\nEngineer,Build apps\n",
            headers={"Content-Type": "application/json"},
        )

    assert unknown.status_code == 422
    assert "recognized job field" in unknown.json()["detail"]
    assert wrong_type.status_code == 415


def test_batch_upload_enforces_csv_size_and_row_count_limits(monkeypatch):
    monkeypatch.setattr(api_module, "predict_job", _assessment)
    with TestClient(app) as client:
        oversized = client.post(
            "/batch-predict",
            content=b"title\n" + b"a" * 1_000_001,
            headers={"Content-Type": "text/csv"},
        )
        rows = ["title"] + [f"Engineer {number}" for number in range(MAX_BATCH_ROWS + 1)]
        too_many_rows = client.post(
            "/batch-predict",
            content=("\n".join(rows) + "\n").encode("utf-8"),
            headers={"Content-Type": "text/csv"},
        )

    assert oversized.status_code == 413
    assert too_many_rows.status_code == 413
    assert f"{MAX_BATCH_ROWS}-job limit" in too_many_rows.json()["detail"]


def test_batch_upload_rejects_invalid_utf8_duplicate_fields_and_malformed_csv():
    with TestClient(app) as client:
        invalid_encoding = client.post(
            "/batch-predict",
            content=b"title,description\nEngineer,\xff\n",
            headers={"Content-Type": "text/csv"},
        )
        duplicate_fields = client.post(
            "/batch-predict",
            content=b"title,job title\nEngineer,Another title\n",
            headers={"Content-Type": "text/csv"},
        )
        malformed_csv = client.post(
            "/batch-predict",
            content=b'title,description\n"unfinished,body\n',
            headers={"Content-Type": "text/csv"},
        )

    assert invalid_encoding.status_code == 422
    assert "UTF-8" in invalid_encoding.json()["detail"]
    assert duplicate_fields.status_code == 422
    assert "duplicate columns" in duplicate_fields.json()["detail"]
    assert malformed_csv.status_code == 422
    assert "Malformed CSV" in malformed_csv.json()["detail"]


def test_batch_report_detects_exact_duplicate_postings_without_returning_source_text(monkeypatch):
    monkeypatch.setattr(api_module, "predict_job", _assessment)
    content = (
        "title,company,description\n"
        '"Data Entry","Example Ltd","Remote data entry role. Pay registration fee immediately."\n'
        '"Data Entry","Example Ltd","Remote data entry role. Pay registration fee immediately."\n'
    )

    with TestClient(app) as client:
        response = client.post(
            "/batch-predict",
            content=content.encode("utf-8"),
            headers={"Content-Type": "text/csv"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["duplicate_pair_count"] == 1
    assert body["duplicate_row_count"] == 2
    assert body["results"][0]["duplicate_matches"][0]["match_type"] == "EXACT_DUPLICATE"
    assert "_duplicate_text" not in body["results"][0]
