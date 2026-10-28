import re
from urllib.parse import urlparse


# ============================================================
# RECRUITMENTGUARD
# URL INTELLIGENCE ENGINE
# ============================================================


SHORTENED_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "ow.ly",
    "is.gd",
    "buff.ly",
    "cutt.ly",
    "shorturl.at",
}


SUSPICIOUS_TLDS = {
    ".xyz",
    ".top",
    ".click",
    ".work",
    ".buzz",
    ".monster",
    ".tk",
    ".ml",
    ".ga",
    ".cf",
}


SUSPICIOUS_KEYWORDS = [
    "verify",
    "urgent",
    "login",
    "payment",
    "fee",
    "register",
    "registration",
    "reward",
    "claim",
    "prize",
    "wallet",
    "bank",
    "password",
    "otp",
]


# ============================================================
# URL EXTRACTION
# ============================================================

def extract_urls(text):

    if not text:
        return []

    pattern = r"https?://[^\s<>\"]+"

    urls = re.findall(
        pattern,
        text,
        flags=re.IGNORECASE
    )

    # Remove duplicate URLs
    return list(dict.fromkeys(urls))


# ============================================================
# DOMAIN EXTRACTION
# ============================================================

def get_domain(url):

    try:

        parsed = urlparse(url)

        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:

        return ""


def normalize_domain(value):

    if not value:
        return ""

    candidate = value.strip()

    if not candidate:
        return ""

    parsed = urlparse(
        candidate if "://" in candidate else f"https://{candidate}"
    )
    domain = (parsed.hostname or "").lower().rstrip(".")

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def verify_application_domains(urls, official_website):

    official_domain = normalize_domain(official_website)
    applications = []

    for url in urls:
        application_domain = get_domain(url)
        matches = bool(
            official_domain
            and application_domain
            and (
                application_domain == official_domain
                or application_domain.endswith(f".{official_domain}")
            )
        )
        applications.append({
            "url": url,
            "domain": application_domain,
            "status": (
                "NOT_PROVIDED"
                if not official_domain
                else "MATCH" if matches else "EXTERNAL"
            ),
        })

    if not official_domain:
        status = "NOT_PROVIDED"
    elif not applications:
        status = "NO_APPLICATION_URL"
    elif any(item["status"] == "EXTERNAL" for item in applications):
        status = "EXTERNAL"
    else:
        status = "MATCH"

    return {
        "status": status,
        "official_domain": official_domain,
        "applications": applications,
        "message": {
            "NOT_PROVIDED": "Add the employer's official website to compare application links.",
            "NO_APPLICATION_URL": "No application URL was found to compare.",
            "EXTERNAL": "At least one application link uses a different domain. Verify it independently; legitimate hiring platforms may also use external domains.",
            "MATCH": "All detected application links use the employer's domain or a subdomain.",
        }[status],
    }


# ============================================================
# URL ANALYSIS
# ============================================================

def analyze_url(url):

    findings = []

    score = 0

    parsed = urlparse(url)

    domain = get_domain(url)

    # --------------------------------------------------------
    # HTTPS CHECK
    # --------------------------------------------------------

    if parsed.scheme.lower() == "https":

        findings.append({
            "type": "HTTPS",
            "severity": "LOW",
            "message": "Secure HTTPS connection detected."
        })

    else:

        score += 25

        findings.append({
            "type": "NO_HTTPS",
            "severity": "HIGH",
            "message": "Job application URL does not use HTTPS."
        })

    # --------------------------------------------------------
    # SHORTENED URL
    # --------------------------------------------------------

    if domain in SHORTENED_DOMAINS:

        score += 30

        findings.append({
            "type": "SHORTENED_URL",
            "severity": "HIGH",
            "message": "URL shortening service detected."
        })

    # --------------------------------------------------------
    # SUSPICIOUS TLD
    # --------------------------------------------------------

    if any(domain.endswith(tld) for tld in SUSPICIOUS_TLDS):

        score += 25

        findings.append({
            "type": "SUSPICIOUS_TLD",
            "severity": "HIGH",
            "message": "Domain uses a potentially suspicious top-level domain."
        })

    # --------------------------------------------------------
    # SUSPICIOUS KEYWORDS
    # --------------------------------------------------------

    url_lower = url.lower()

    matched_keywords = [
        keyword
        for keyword in SUSPICIOUS_KEYWORDS
        if keyword in url_lower
    ]

    if matched_keywords:

        score += min(
            len(matched_keywords) * 8,
            25
        )

        findings.append({
            "type": "SUSPICIOUS_KEYWORDS",
            "severity": "MEDIUM",
            "message": (
                "Suspicious URL keywords detected: "
                + ", ".join(matched_keywords)
            )
        })

    # --------------------------------------------------------
    # IP ADDRESS URL
    # --------------------------------------------------------

    ip_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"

    if re.match(ip_pattern, domain):

        score += 30

        findings.append({
            "type": "IP_ADDRESS",
            "severity": "HIGH",
            "message": "URL uses an IP address instead of a domain name."
        })

    # --------------------------------------------------------
    # EXCESSIVE URL LENGTH
    # --------------------------------------------------------

    if len(url) > 150:

        score += 10

        findings.append({
            "type": "LONG_URL",
            "severity": "MEDIUM",
            "message": "Unusually long URL detected."
        })

    # --------------------------------------------------------
    # FINAL SCORE
    # --------------------------------------------------------

    score = min(score, 100)

    if score >= 70:

        risk_level = "CRITICAL"

    elif score >= 50:

        risk_level = "HIGH"

    elif score >= 30:

        risk_level = "MEDIUM"

    else:

        risk_level = "LOW"

    return {
        "url": url,
        "domain": domain,
        "url_risk_score": round(score, 2),
        "risk_level": risk_level,
        "findings": findings
    }


# ============================================================
# COMPLETE URL INTELLIGENCE
# ============================================================

def analyze_urls(text, official_website=""):

    urls = extract_urls(text)
    domain_verification = verify_application_domains(
        urls,
        official_website
    )

    if not urls:

        return {
            "urls_detected": 0,
            "overall_url_risk": 0,
            "risk_level": "LOW",
            "urls": [],
            "message": "No URLs detected in the job posting.",
            "domain_verification": domain_verification,
        }

    results = [
        analyze_url(url)
        for url in urls
    ]

    overall_score = max(
        result["url_risk_score"]
        for result in results
    )

    if overall_score >= 70:

        overall_level = "CRITICAL"

    elif overall_score >= 50:

        overall_level = "HIGH"

    elif overall_score >= 30:

        overall_level = "MEDIUM"

    else:

        overall_level = "LOW"

    return {
        "urls_detected": len(urls),
        "overall_url_risk": round(
            overall_score,
            2
        ),
        "risk_level": overall_level,
        "urls": results,
        "domain_verification": domain_verification,
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    sample_text = """
    Congratulations! You have been selected.

    Apply immediately using:
    http://bit.ly/urgent-job-payment

    Pay the registration fee to confirm your position.
    """

    print("=" * 60)
    print("RECRUITMENTGUARD")
    print("URL INTELLIGENCE ENGINE TEST")
    print("=" * 60)

    result = analyze_urls(sample_text)

    print(
        f"\nURLs Detected : {result['urls_detected']}"
    )

    print(
        f"Overall URL Risk : "
        f"{result['overall_url_risk']}%"
    )

    print(
        f"Risk Level : "
        f"{result['risk_level']}"
    )

    for item in result["urls"]:

        print("\nURL:", item["url"])

        print(
            "Domain:",
            item["domain"]
        )

        print(
            "Risk Score:",
            item["url_risk_score"]
        )

        print(
            "Risk Level:",
            item["risk_level"]
        )

        for finding in item["findings"]:

            print(
                f"  [{finding['severity']}] "
                f"{finding['type']} - "
                f"{finding['message']}"
            )

    print("\n" + "=" * 60)
    print("URL INTELLIGENCE ANALYSIS COMPLETED")
    print("=" * 60)