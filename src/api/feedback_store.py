import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIN_VERIFIED_FEEDBACK_FOR_METRICS = 10


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                prediction_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model_prediction TEXT NOT NULL,
                fraud_probability REAL NOT NULL,
                risk_level TEXT NOT NULL,
                final_risk_score REAL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id TEXT NOT NULL REFERENCES analyses(prediction_id),
                title TEXT NOT NULL,
                model_prediction TEXT NOT NULL,
                fraud_probability REAL NOT NULL,
                risk_level TEXT NOT NULL,
                final_risk_score REAL,
                user_label TEXT NOT NULL CHECK (user_label IN ('FRAUDULENT', 'LEGITIMATE')),
                comment TEXT NOT NULL DEFAULT '',
                submitted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                review_status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (review_status IN ('PENDING', 'REVIEWED')),
                review_label TEXT CHECK (review_label IN ('FRAUDULENT', 'LEGITIMATE')),
                review_decision TEXT CHECK (
                    review_decision IN ('VERIFIED_FRAUDULENT', 'VERIFIED_LEGITIMATE', 'REJECTED')
                ),
                reviewer_identity TEXT,
                review_note TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT
            )
            """
        )
        for table, column, definition in (
            ("analyses", "final_risk_score", "REAL"),
            ("feedback", "final_risk_score", "REAL"),
            (
                "feedback",
                "review_decision",
                "TEXT CHECK (review_decision IN ('VERIFIED_FRAUDULENT', 'VERIFIED_LEGITIMATE', 'REJECTED'))",
            ),
            ("feedback", "reviewer_identity", "TEXT"),
        ):
            columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
            if column not in columns:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        connection.execute(
            """
            UPDATE feedback
            SET review_decision = CASE review_label
                    WHEN 'FRAUDULENT' THEN 'VERIFIED_FRAUDULENT'
                    WHEN 'LEGITIMATE' THEN 'VERIFIED_LEGITIMATE'
                END,
                reviewer_identity = 'legacy-admin-review'
            WHERE review_status = 'REVIEWED'
                AND review_label IS NOT NULL
                AND review_decision IS NULL
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_review_status ON feedback(review_status)"
        )
        connection.commit()
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _database_path() -> Path:
    configured_path = os.getenv("RECRUITMENTGUARD_FEEDBACK_DB")
    return Path(configured_path) if configured_path else PROJECT_ROOT / "data" / "feedback.sqlite3"


def create_analysis(
    *,
    prediction_id: str,
    title: str,
    model_prediction: str,
    fraud_probability: float,
    risk_level: str,
    final_risk_score: float | None = None,
) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO analyses (
                prediction_id, title, model_prediction, fraud_probability, risk_level,
                final_risk_score
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (prediction_id, title, model_prediction, fraud_probability, risk_level, final_risk_score),
        )


def create_feedback(
    *,
    prediction_id: str,
    user_label: str,
    comment: str,
) -> dict[str, Any] | None:
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        analysis = connection.execute(
            "SELECT * FROM analyses WHERE prediction_id = ?", (prediction_id,)
        ).fetchone()
        if analysis is None:
            return None
        existing_feedback = connection.execute(
            "SELECT * FROM feedback WHERE prediction_id = ? ORDER BY id LIMIT 1",
            (prediction_id,),
        ).fetchone()
        if existing_feedback is not None:
            return {**dict(existing_feedback), "already_submitted": True}
        cursor = connection.execute(
            """
            INSERT INTO feedback (
                prediction_id, title, model_prediction, fraud_probability,
                risk_level, final_risk_score, user_label, comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prediction_id,
                analysis["title"],
                analysis["model_prediction"],
                analysis["fraud_probability"],
                analysis["risk_level"],
                analysis["final_risk_score"],
                user_label,
                comment,
            ),
        )
        row = connection.execute(
            "SELECT * FROM feedback WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return {**dict(row), "already_submitted": False}


def list_feedback(review_status: str | None = None) -> list[dict[str, Any]]:
    with _connect() as connection:
        if review_status is None:
            rows = connection.execute(
                "SELECT * FROM feedback ORDER BY submitted_at DESC, id DESC"
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM feedback
                WHERE review_status = ?
                ORDER BY submitted_at DESC, id DESC
                """,
                (review_status,),
            ).fetchall()
        return [dict(row) for row in rows]


def list_verified_feedback() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM feedback
            WHERE review_decision IN ('VERIFIED_FRAUDULENT', 'VERIFIED_LEGITIMATE')
            ORDER BY submitted_at DESC, id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def get_summary() -> dict[str, Any]:
    with _connect() as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM feedback"
        ).fetchone()[0]
        statuses = connection.execute(
            "SELECT review_status, COUNT(*) AS count FROM feedback GROUP BY review_status"
        ).fetchall()
        labels = connection.execute(
            "SELECT user_label, COUNT(*) AS count FROM feedback GROUP BY user_label"
        ).fetchall()
        return {
            "total_feedback": total,
            "review_status_counts": {row["review_status"]: row["count"] for row in statuses},
            "user_label_counts": {row["user_label"]: row["count"] for row in labels},
        }


def get_analytics() -> dict[str, Any]:
    with _connect() as connection:
        total = connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        user_label_rows = connection.execute(
            "SELECT user_label, COUNT(*) AS count FROM feedback GROUP BY user_label"
        ).fetchall()
        pending_count = connection.execute(
            "SELECT COUNT(*) FROM feedback WHERE review_status = 'PENDING'"
        ).fetchone()[0]
        verified_rows = connection.execute(
            """
            SELECT model_prediction, review_decision
            FROM feedback
            WHERE review_status = 'REVIEWED'
                AND review_decision IN ('VERIFIED_FRAUDULENT', 'VERIFIED_LEGITIMATE')
            """
        ).fetchall()
        decision_rows = connection.execute(
            "SELECT review_decision, COUNT(*) AS count FROM feedback GROUP BY review_decision"
        ).fetchall()
        trend_rows = connection.execute(
            """
            SELECT date(submitted_at) AS day, COUNT(*) AS count
            FROM feedback
            WHERE date(submitted_at) IS NOT NULL
            GROUP BY date(submitted_at)
            ORDER BY day
            """
        ).fetchall()

    label_counts = {row["user_label"]: row["count"] for row in user_label_rows}
    decision_counts = {row["review_decision"]: row["count"] for row in decision_rows}
    verified_count = len(verified_rows)
    valid_pairs = [
        (row["model_prediction"], row["review_decision"].removeprefix("VERIFIED_"))
        for row in verified_rows
        if row["model_prediction"] in {"FRAUDULENT", "LEGITIMATE"}
        and row["review_decision"] in {"VERIFIED_FRAUDULENT", "VERIFIED_LEGITIMATE"}
    ]
    true_labels = {actual for _, actual in valid_pairs}
    enough_verified_data = (
        len(valid_pairs) >= MIN_VERIFIED_FEEDBACK_FOR_METRICS
        and true_labels == {"FRAUDULENT", "LEGITIMATE"}
    )

    evaluation: dict[str, Any] = {
        "available": False,
        "positive_class": "FRAUDULENT",
        "verified_records": len(valid_pairs),
        "minimum_records": MIN_VERIFIED_FEEDBACK_FOR_METRICS,
    }
    if enough_verified_data:
        true_negatives = sum(
            predicted == "LEGITIMATE" and actual == "LEGITIMATE"
            for predicted, actual in valid_pairs
        )
        false_positives = sum(
            predicted == "FRAUDULENT" and actual == "LEGITIMATE"
            for predicted, actual in valid_pairs
        )
        false_negatives = sum(
            predicted == "LEGITIMATE" and actual == "FRAUDULENT"
            for predicted, actual in valid_pairs
        )
        true_positives = sum(
            predicted == "FRAUDULENT" and actual == "FRAUDULENT"
            for predicted, actual in valid_pairs
        )
        precision = true_positives / (true_positives + false_positives) if (
            true_positives + false_positives
        ) else 0.0
        recall = true_positives / (true_positives + false_negatives) if (
            true_positives + false_negatives
        ) else 0.0
        f1_score = 2 * precision * recall / (precision + recall) if (
            precision + recall
        ) else 0.0
        evaluation.update(
            {
                "available": True,
                "true_positives": true_positives,
                "true_negatives": true_negatives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "confusion_matrix": [
                    [true_negatives, false_positives],
                    [false_negatives, true_positives],
                ],
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1_score, 4),
            }
        )

    trends = [dict(row) for row in trend_rows] if len(trend_rows) >= 2 else []
    return {
        "total_submissions": total,
        "user_submitted_label_counts": {
            "FRAUDULENT": label_counts.get("FRAUDULENT", 0),
            "LEGITIMATE": label_counts.get("LEGITIMATE", 0),
        },
        "pending_count": pending_count,
        "reviewed_verified_count": verified_count,
        "verified_label_counts": {
            "FRAUDULENT": decision_counts.get("VERIFIED_FRAUDULENT", 0),
            "LEGITIMATE": decision_counts.get("VERIFIED_LEGITIMATE", 0),
        },
        "rejected_count": decision_counts.get("REJECTED", 0),
        "trends": trends,
        "evaluation": evaluation,
    }


def review_feedback(
    feedback_id: int,
    *,
    decision: str,
    review_note: str,
    reviewer_identity: str,
) -> dict[str, Any] | None:
    review_label = {
        "VERIFIED_FRAUDULENT": "FRAUDULENT",
        "VERIFIED_LEGITIMATE": "LEGITIMATE",
    }.get(decision)
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE feedback
            SET review_status = 'REVIEWED',
                review_label = ?,
                review_decision = ?,
                reviewer_identity = ?,
                review_note = ?,
                reviewed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ? AND review_status = 'PENDING'
            """,
            (review_label, decision, reviewer_identity, review_note, feedback_id),
        )
        if cursor.rowcount == 0:
            return None
        row = connection.execute(
            "SELECT * FROM feedback WHERE id = ?", (feedback_id,)
        ).fetchone()
        return dict(row)
