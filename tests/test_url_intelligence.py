from src.url_intelligence.url_analyzer import analyze_urls


def test_application_subdomain_matches_official_website():
    result = analyze_urls(
        "Apply at https://careers.example.com/jobs/1",
        "https://www.example.com/about",
    )

    verification = result["domain_verification"]
    assert verification["status"] == "MATCH"
    assert verification["official_domain"] == "example.com"
    assert verification["applications"][0]["status"] == "MATCH"


def test_external_application_domain_is_informational():
    result = analyze_urls(
        "Apply at https://jobs.example.net/role",
        "example.com",
    )

    verification = result["domain_verification"]
    assert verification["status"] == "EXTERNAL"
    assert verification["applications"][0]["status"] == "EXTERNAL"
    assert result["overall_url_risk"] == 0


def test_domain_check_handles_missing_website_and_urls():
    missing_website = analyze_urls("Apply at https://example.com/job")
    missing_urls = analyze_urls("No links in this posting", "example.com")

    assert missing_website["domain_verification"]["status"] == "NOT_PROVIDED"
    assert missing_urls["domain_verification"]["status"] == "NO_APPLICATION_URL"