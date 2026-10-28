import sqlite3

from src.api import feedback_store


def test_feedback_is_tied_to_analysis_and_can_be_reviewed(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "RECRUITMENTGUARD_FEEDBACK_DB",
        str(tmp_path / "feedback.sqlite3"),
    )
    feedback_store.create_analysis(
        prediction_id="analysis-1",
        title="Data entry role",
        model_prediction="FRAUDULENT",
        fraud_probability=0.91,
        risk_level="HIGH",
        final_risk_score=84,
    )

    feedback = feedback_store.create_feedback(
        prediction_id="analysis-1",
        user_label="LEGITIMATE",
        comment="I verified the employer website.",
    )

    assert feedback is not None
    assert feedback["title"] == "Data entry role"
    assert feedback["final_risk_score"] == 84
    assert feedback["review_status"] == "PENDING"
    assert feedback["already_submitted"] is False
    assert feedback_store.get_summary()["total_feedback"] == 1
    duplicate = feedback_store.create_feedback(
        prediction_id="analysis-1",
        user_label="FRAUDULENT",
        comment="Duplicate request",
    )
    assert duplicate is not None
    assert duplicate["already_submitted"] is True
    assert feedback_store.get_summary()["total_feedback"] == 1
    assert feedback_store.create_feedback(
        prediction_id="missing-analysis",
        user_label="LEGITIMATE",
        comment="",
    ) is None

    reviewed = feedback_store.review_feedback(
        feedback["id"],
        decision="VERIFIED_LEGITIMATE",
        review_note="Employer confirmed independently.",
        reviewer_identity="reviewer-test",
    )

    assert reviewed is not None
    assert reviewed["review_status"] == "REVIEWED"
    assert reviewed["review_label"] == "LEGITIMATE"
    assert reviewed["review_decision"] == "VERIFIED_LEGITIMATE"
    assert reviewed["reviewer_identity"] == "reviewer-test"
    assert reviewed["reviewed_at"]
    assert feedback_store.get_summary()["review_status_counts"] == {"REVIEWED": 1}


def test_reviewing_unknown_feedback_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "RECRUITMENTGUARD_FEEDBACK_DB",
        str(tmp_path / "feedback.sqlite3"),
    )

    assert feedback_store.review_feedback(
        404,
        decision="VERIFIED_FRAUDULENT",
        review_note="",
        reviewer_identity="reviewer-test",
    ) is None


def test_analytics_use_only_verified_labels_for_error_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "RECRUITMENTGUARD_FEEDBACK_DB",
        str(tmp_path / "feedback.sqlite3"),
    )
    actual_labels = ["LEGITIMATE"] * 5 + ["FRAUDULENT"] * 5
    predicted_labels = [
        "LEGITIMATE", "LEGITIMATE", "FRAUDULENT", "FRAUDULENT", "FRAUDULENT",
        "FRAUDULENT", "FRAUDULENT", "LEGITIMATE", "LEGITIMATE", "LEGITIMATE",
    ]

    for index, (actual, predicted) in enumerate(zip(actual_labels, predicted_labels)):
        prediction_id = f"analysis-{index}"
        feedback_store.create_analysis(
            prediction_id=prediction_id,
            title="Test posting",
            model_prediction=predicted,
            fraud_probability=0.5,
            risk_level="MEDIUM",
            final_risk_score=50,
        )
        feedback = feedback_store.create_feedback(
            prediction_id=prediction_id,
            user_label="LEGITIMATE" if index == 0 else "FRAUDULENT",
            comment="",
        )
        assert feedback is not None
        feedback_store.review_feedback(
            feedback["id"],
            decision=f"VERIFIED_{actual}",
            reviewer_identity="reviewer-test",
            review_note="Independently checked",
        )

    analytics = feedback_store.get_analytics()
    evaluation = analytics["evaluation"]

    assert analytics["total_submissions"] == 10
    assert analytics["reviewed_verified_count"] == 10
    assert analytics["user_submitted_label_counts"] == {"FRAUDULENT": 9, "LEGITIMATE": 1}
    assert evaluation["available"] is True
    assert evaluation["positive_class"] == "FRAUDULENT"
    assert evaluation["confusion_matrix"] == [[2, 3], [3, 2]]
    assert evaluation["precision"] == 0.4
    assert evaluation["recall"] == 0.4
    assert evaluation["f1_score"] == 0.4


def test_analytics_hide_metrics_when_verified_sample_is_small(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "RECRUITMENTGUARD_FEEDBACK_DB",
        str(tmp_path / "feedback.sqlite3"),
    )
    analytics = feedback_store.get_analytics()

    assert analytics["total_submissions"] == 0
    assert analytics["trends"] == []
    assert analytics["evaluation"]["available"] is False


def test_pending_and_rejected_feedback_are_not_verified_ground_truth(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "RECRUITMENTGUARD_FEEDBACK_DB",
        str(tmp_path / "feedback.sqlite3"),
    )
    for prediction_id in ("pending", "rejected"):
        feedback_store.create_analysis(
            prediction_id=prediction_id,
            title="Test posting",
            model_prediction="FRAUDULENT",
            fraud_probability=0.8,
            risk_level="HIGH",
            final_risk_score=80,
        )
    pending = feedback_store.create_feedback(
        prediction_id="pending",
        user_label="LEGITIMATE",
        comment="",
    )
    rejected = feedback_store.create_feedback(
        prediction_id="rejected",
        user_label="FRAUDULENT",
        comment="",
    )
    assert pending is not None and rejected is not None
    feedback_store.review_feedback(
        rejected["id"],
        decision="REJECTED",
        review_note="Could not verify the report.",
        reviewer_identity="reviewer-test",
    )

    analytics = feedback_store.get_analytics()

    assert analytics["pending_count"] == 1
    assert analytics["rejected_count"] == 1
    assert analytics["reviewed_verified_count"] == 0
    assert analytics["verified_label_counts"] == {"FRAUDULENT": 0, "LEGITIMATE": 0}
    assert analytics["evaluation"]["verified_records"] == 0
    assert analytics["evaluation"]["available"] is False
    assert feedback_store.list_verified_feedback() == []


def test_existing_reviewed_labels_migrate_to_verified_decisions(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy-feedback.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE analyses (
            prediction_id TEXT PRIMARY KEY, title TEXT NOT NULL,
            model_prediction TEXT NOT NULL, fraud_probability REAL NOT NULL,
            risk_level TEXT NOT NULL, final_risk_score REAL,
            created_at TEXT NOT NULL DEFAULT 'legacy'
        );
        CREATE TABLE feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id TEXT NOT NULL REFERENCES analyses(prediction_id),
            title TEXT NOT NULL, model_prediction TEXT NOT NULL,
            fraud_probability REAL NOT NULL, risk_level TEXT NOT NULL,
            final_risk_score REAL,
            user_label TEXT NOT NULL CHECK (user_label IN ('FRAUDULENT', 'LEGITIMATE')),
            comment TEXT NOT NULL DEFAULT '', submitted_at TEXT NOT NULL DEFAULT 'legacy',
            review_status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK (review_status IN ('PENDING', 'REVIEWED')),
            review_label TEXT CHECK (review_label IN ('FRAUDULENT', 'LEGITIMATE')),
            review_note TEXT NOT NULL DEFAULT '', reviewed_at TEXT
        );
        INSERT INTO analyses VALUES ('legacy-1', 'Role', 'FRAUDULENT', 0.9, 'HIGH', 90, 'legacy');
        INSERT INTO feedback (
            prediction_id, title, model_prediction, fraud_probability, risk_level,
            final_risk_score, user_label, review_status, review_label, reviewed_at
        ) VALUES (
            'legacy-1', 'Role', 'FRAUDULENT', 0.9, 'HIGH', 90,
            'LEGITIMATE', 'REVIEWED', 'LEGITIMATE', 'legacy'
        );
        """
    )
    connection.close()
    monkeypatch.setenv("RECRUITMENTGUARD_FEEDBACK_DB", str(database_path))

    analytics = feedback_store.get_analytics()
    migrated_record = feedback_store.list_verified_feedback()[0]

    assert analytics["reviewed_verified_count"] == 1
    assert analytics["verified_label_counts"] == {"FRAUDULENT": 0, "LEGITIMATE": 1}
    assert migrated_record["review_decision"] == "VERIFIED_LEGITIMATE"
    assert migrated_record["reviewer_identity"] == "legacy-admin-review"
