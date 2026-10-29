from fastapi.testclient import TestClient

from src.api.app import app


def test_feedback_submission_and_protected_review_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "RECRUITMENTGUARD_FEEDBACK_DB",
        str(tmp_path / "feedback.sqlite3"),
    )
    monkeypatch.delenv("RECRUITMENTGUARD_ADMIN_KEY", raising=False)
    monkeypatch.setenv("RECRUITMENTGUARD_REVIEWER_IDENTITY", "authorized-test-reviewer")

    with TestClient(app) as client:
        analysis = client.post(
            "/predict",
            json={
                "title": "Customer support associate",
                "description": "Join our customer support team. Salary and benefits are provided.",
            },
        )
        assert analysis.status_code == 200
        analysis_id = analysis.json()["analysis_id"]

        submitted = client.post(
            "/feedback",
            json={
                "prediction_id": analysis_id,
                "user_label": "FRAUDULENT",
                "comment": "The employer requested an upfront fee.",
            },
        )
        assert submitted.status_code == 201
        assert submitted.json()["feedback_id"] == 1
        assert submitted.json()["message"] == "Feedback submitted successfully. Your report is pending verification."

        disabled = client.get("/admin/feedback/summary")
        assert disabled.status_code == 503

        monkeypatch.setenv("RECRUITMENTGUARD_ADMIN_KEY", "test-admin-key")
        unauthorized = client.get(
            "/admin/feedback/summary",
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert unauthorized.status_code == 401

        pending = client.get(
            "/admin/feedback?review_status=PENDING",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert pending.status_code == 200
        assert pending.json()["feedback"][0]["title"] == "Customer support associate"

        reviewed = client.post(
            "/admin/feedback/1/review",
            headers={"X-Admin-Key": "test-admin-key"},
            json={"decision": "VERIFIED_FRAUDULENT", "review_note": "Confirmed fee request."},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["feedback"]["review_status"] == "REVIEWED"
        assert reviewed.json()["feedback"]["review_decision"] == "VERIFIED_FRAUDULENT"
        assert reviewed.json()["feedback"]["reviewer_identity"] == "authorized-test-reviewer"
        assert reviewed.json()["feedback"]["reviewed_at"]

        exported = client.get(
            "/admin/feedback/export",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert exported.status_code == 200
        assert "Customer support associate" in exported.text
        assert "FRAUDULENT" in exported.text


def test_feedback_analytics_endpoint_returns_aggregate_only(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "RECRUITMENTGUARD_FEEDBACK_DB",
        str(tmp_path / "feedback.sqlite3"),
    )

    with TestClient(app) as client:
        response = client.get("/feedback/analytics")
        unsupported_method = client.post("/feedback/analytics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "total_submissions": 0,
        "user_submitted_label_counts": {"FRAUDULENT": 0, "LEGITIMATE": 0},
        "pending_count": 0,
        "reviewed_verified_count": 0,
        "verified_label_counts": {"FRAUDULENT": 0, "LEGITIMATE": 0},
        "rejected_count": 0,
        "trends": [],
        "evaluation": {
            "available": False,
            "positive_class": "FRAUDULENT",
            "verified_records": 0,
            "minimum_records": 10,
        },
    }
    assert "feedback" not in response.json()
    assert unsupported_method.status_code == 405


def test_feedback_analytics_allows_deployed_vercel_origin(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "RECRUITMENTGUARD_FEEDBACK_DB",
        str(tmp_path / "feedback.sqlite3"),
    )
    frontend_origin = "https://recruitment-scam-detection.vercel.app"

    with TestClient(app) as client:
        response = client.options(
            "/feedback/analytics",
            headers={
                "Origin": frontend_origin,
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == frontend_origin


def test_rejected_feedback_does_not_count_as_verified(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "RECRUITMENTGUARD_FEEDBACK_DB",
        str(tmp_path / "feedback.sqlite3"),
    )
    monkeypatch.setenv("RECRUITMENTGUARD_ADMIN_KEY", "test-admin-key")

    with TestClient(app) as client:
        analysis = client.post(
            "/predict",
            json={"title": "Test role", "description": "A normal paid role with clear requirements."},
        ).json()
        submitted = client.post(
            "/feedback",
            json={
                "prediction_id": analysis["analysis_id"],
                "user_label": "FRAUDULENT",
                "comment": "Unable to confirm this report.",
            },
        )
        assert submitted.status_code == 201

        unauthorized = client.post(
            "/admin/feedback/1/review",
            json={"decision": "REJECTED"},
        )
        assert unauthorized.status_code == 401

        rejected = client.post(
            "/admin/feedback/1/review",
            headers={"X-Admin-Key": "test-admin-key"},
            json={"decision": "REJECTED", "review_note": "Insufficient evidence."},
        )
        assert rejected.status_code == 200
        assert rejected.json()["feedback"]["review_label"] is None
        analytics = client.get("/feedback/analytics").json()
        assert analytics["rejected_count"] == 1
        assert analytics["reviewed_verified_count"] == 0
        assert analytics["evaluation"]["verified_records"] == 0
