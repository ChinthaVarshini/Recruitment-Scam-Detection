import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_URL = "http://127.0.0.1:8000"


class ApiSmokeTests(unittest.TestCase):
    def request(self, path, method="GET", payload=None):
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            f"{API_URL}{path}",
            data=body,
            headers=headers,
            method=method,
        )

        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())

    def test_health_reports_loaded_artifacts(self):
        status, response = self.request("/health")

        self.assertEqual(status, 200)
        self.assertEqual(response["status"], "healthy")
        self.assertTrue(response["model_loaded"])
        self.assertTrue(response["vectorizer_loaded"])

    def test_prediction_returns_risk_assessment(self):
        payload = {
            "title": "Software Engineer",
            "location": "Hyderabad / Remote",
            "company_profile": "Established technology company",
            "description": "Build web applications with a collaborative engineering team.",
            "requirements": "Python, JavaScript, and two years experience",
            "benefits": "Salary and health insurance",
        }
        status, response = self.request("/predict", "POST", payload)

        self.assertEqual(status, 200)
        self.assertIn(response["prediction"], {"LEGITIMATE", "FRAUDULENT"})
        self.assertIn(response["risk_level"], {"LOW", "MEDIUM", "HIGH", "CRITICAL"})
        self.assertIsInstance(response["risk_indicators"], list)
        self.assertIsInstance(response["recommendations"], list)

    def test_empty_prediction_is_rejected(self):
        with self.assertRaises(HTTPError) as error:
            self.request("/predict", "POST", {})

        self.assertEqual(error.exception.code, 400)


if __name__ == "__main__":
    unittest.main()