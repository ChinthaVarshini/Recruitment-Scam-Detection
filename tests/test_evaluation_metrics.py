import numpy as np

from src.evaluation.evaluate_models import calculate_metrics


def test_metrics_report_fraud_detection_and_confusion_counts():
    metrics = calculate_metrics(
        np.array([0, 0, 1, 1]),
        np.array([0, 1, 1, 0]),
        np.array([0.1, 0.7, 0.9, 0.4]),
    )

    assert metrics["test_rows"] == 4
    assert metrics["legitimate_rows"] == 2
    assert metrics["fraudulent_rows"] == 2
    assert metrics["fraud_recall"] == 0.5
    assert metrics["specificity"] == 0.5
    assert metrics["g_mean"] == 0.5
    assert metrics["confusion_matrix"] == [[1, 1], [1, 1]]
