import io
import socket

import pytest

from src.url_intelligence import job_page_scanner
from src.url_intelligence.job_page_scanner import (
    JobPageScanError,
    _open_pinned_connection,
    _validate_public_url,
    extract_job_details,
    scan_job_page,
)


JOB_PAGE = """
<html><head><title>Old title</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "Junior Data Analyst",
  "description": "<p>Collect data and pay a registration fee to apply.</p>",
  "hiringOrganization": {"@type": "Organization", "name": "Example Hiring", "url": "https://example.test"},
  "jobLocation": {"address": {"addressLocality": "Hyderabad", "addressRegion": "Telangana"}},
  "qualifications": "Python experience",
  "jobBenefits": "Health insurance"
}
</script></head><body><main><p>Ignored fallback text.</p></main></body></html>
"""


def _public_dns(*args, **kwargs):
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
    ]


def _wire_response(status, headers, body=b""):
    reason = {200: "OK", 302: "Found", 301: "Moved Permanently"}.get(status, "Response")
    values = dict(headers)
    values.setdefault("Connection", "close")
    if body:
        values.setdefault("Content-Length", str(len(body)))
    head = "".join(f"{name}: {value}\r\n" for name, value in values.items())
    return f"HTTP/1.1 {status} {reason}\r\n{head}\r\n".encode("ascii") + body


class FakeSocket:
    def __init__(self, peer, response_bytes):
        self.peer = peer
        self.response_bytes = response_bytes
        self.sent = b""
        self.closed = False

    def getpeername(self):
        return (self.peer, 443)

    def settimeout(self, _timeout):
        pass

    def sendall(self, data):
        self.sent += data

    def makefile(self, _mode):
        return io.BytesIO(self.response_bytes)

    def close(self):
        self.closed = True


def _mock_connection(monkeypatch, peer, response_bytes, calls=None):
    def open_connection(address, port, scheme, server_name):
        if calls is not None:
            calls.append((address, port, scheme, server_name))
        return FakeSocket(peer, response_bytes)

    monkeypatch.setattr(job_page_scanner, "_open_pinned_connection", open_connection)


def test_private_addresses_and_nonstandard_ports_are_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
    ])
    with pytest.raises(JobPageScanError, match="private network"):
        _validate_public_url("https://jobs.example.test/posting")

    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    with pytest.raises(JobPageScanError, match="standard HTTP"):
        _validate_public_url("https://jobs.example.test:8443/posting")
    with pytest.raises(JobPageScanError, match="public HTTP and HTTPS"):
        _validate_public_url("file:///C:/Windows/win.ini")


def test_dns_mixed_public_and_private_addresses_are_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443)),
    ])

    with pytest.raises(JobPageScanError, match="private network"):
        _validate_public_url("https://jobs.example.test/posting")


def test_dns_nxdomain_is_reported_as_unresolved_not_as_a_risk(monkeypatch):
    def unresolved(*_args, **_kwargs):
        raise socket.gaierror(socket.EAI_NONAME, "name does not exist")

    monkeypatch.setattr(socket, "getaddrinfo", unresolved)

    with pytest.raises(JobPageScanError, match="hostname does not exist") as error:
        _validate_public_url("https://missing.example.test/jobs")

    assert error.value.code == "hostname_unresolved"


def test_temporary_dns_failure_is_distinguished_from_nxdomain(monkeypatch):
    def temporary_failure(*_args, **_kwargs):
        raise socket.gaierror(socket.EAI_AGAIN, "temporary failure")

    monkeypatch.setattr(socket, "getaddrinfo", temporary_failure)

    with pytest.raises(JobPageScanError, match="temporarily unavailable") as error:
        _validate_public_url("https://temporary.example.test/jobs")

    assert error.value.code == "dns_temporary_failure"


def test_dns_resolution_has_a_deadline(monkeypatch):
    class TimedOutFuture:
        def result(self, timeout):
            assert timeout == job_page_scanner.DNS_RESOLUTION_TIMEOUT
            raise job_page_scanner.FutureTimeoutError()

        def cancel(self):
            return True

    class TimedOutExecutor:
        def submit(self, *_args, **_kwargs):
            return TimedOutFuture()

    monkeypatch.setattr(job_page_scanner, "_DNS_EXECUTOR", TimedOutExecutor())

    with pytest.raises(JobPageScanError, match="DNS lookup timed out") as error:
        _validate_public_url("https://slow-dns.example.test/jobs")

    assert error.value.code == "dns_timeout"


def test_jobposting_json_ld_fields_are_extracted():
    details = extract_job_details(JOB_PAGE, "https://jobs.example.test/role")

    assert details["title"] == "Junior Data Analyst"
    assert details["company_profile"] == "Example Hiring"
    assert details["company_website"] == "https://example.test"
    assert "Hyderabad" in details["location"]
    assert "Telangana" in details["location"]
    assert "registration fee" in details["description"]
    assert details["requirements"] == "Python experience"
    assert details["benefits"] == "Health insurance"
    assert details["scanned_url"] == "https://jobs.example.test/role"


def test_job_page_fetch_uses_pinned_public_peer_and_supports_empty_redirect(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    calls = []
    redirect = _wire_response(
        301,
        {"Location": "https://job-boards.example.test/open/role", "Content-Length": "0"},
    )
    page = _wire_response(
        200,
        {"Content-Type": "text/html; charset=utf-8"},
        JOB_PAGE.encode("utf-8"),
    )
    responses = iter([redirect, page])

    def open_connection(address, port, scheme, server_name):
        calls.append((address, port, scheme, server_name))
        return FakeSocket(
            "93.184.216.34",
            next(responses),
        )

    monkeypatch.setattr(job_page_scanner, "_open_pinned_connection", open_connection)
    details = scan_job_page("https://jobs.example.test/role")

    assert details["title"] == "Junior Data Analyst"
    assert details["scanned_url"] == "https://job-boards.example.test/open/role"
    assert len(calls) == 2
    assert all(call[0] == "93.184.216.34" for call in calls)


def test_job_page_request_rejects_unexpected_connected_peer(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    _mock_connection(
        monkeypatch,
        "10.0.0.8",
        _wire_response(200, {"Content-Type": "text/html"}, JOB_PAGE.encode()),
    )

    with pytest.raises(JobPageScanError, match="unexpected address"):
        scan_job_page("https://jobs.example.test/role")


def test_job_page_request_rejects_oversized_declared_response(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    response = _wire_response(
        200,
        {
            "Content-Type": "text/html",
            "Content-Length": str(job_page_scanner.MAX_PAGE_BYTES + 1),
        },
    )
    _mock_connection(monkeypatch, "93.184.216.34", response)

    with pytest.raises(JobPageScanError, match="2 MB"):
        scan_job_page("https://jobs.example.test/role")


def test_job_page_http_errors_are_reported_explicitly(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    _mock_connection(
        monkeypatch,
        "93.184.216.34",
        _wire_response(503, {"Content-Type": "text/html"}),
    )

    with pytest.raises(JobPageScanError, match="HTTP 503") as error:
        scan_job_page("https://jobs.example.test/role")

    assert error.value.code == "upstream_http_error"


def test_job_page_connection_timeout_is_not_reported_as_dns_failure(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)

    def timeout(*_args, **_kwargs):
        raise socket.timeout("connection timed out")

    monkeypatch.setattr(job_page_scanner, "_open_pinned_connection", timeout)

    with pytest.raises(JobPageScanError, match="connection timed out") as error:
        scan_job_page("https://jobs.example.test/role")

    assert error.value.code == "connection_timeout"


def test_redirect_to_private_address_is_blocked_before_second_request(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    calls = []
    _mock_connection(
        monkeypatch,
        "93.184.216.34",
        _wire_response(
            302,
            {"Location": "http://127.0.0.1/private", "Content-Length": "0"},
        ),
        calls,
    )

    with pytest.raises(JobPageScanError, match="private network"):
        scan_job_page("https://jobs.example.test/role")
    assert len(calls) == 1


def test_https_connection_uses_hostname_for_certificate_verification(monkeypatch):
    raw_socket = FakeSocket("93.184.216.34", b"")
    observed = {}

    class FakeTLSContext:
        def wrap_socket(self, connection, *, server_hostname):
            observed["connection"] = connection
            observed["server_hostname"] = server_hostname
            return connection

    monkeypatch.setattr(
        job_page_scanner.socket,
        "create_connection",
        lambda address, timeout: (observed.update(address=address, timeout=timeout) or raw_socket),
    )
    monkeypatch.setattr(
        job_page_scanner.ssl,
        "create_default_context",
        FakeTLSContext,
    )

    result = _open_pinned_connection(
        "93.184.216.34",
        443,
        "https",
        "jobs.example.test",
    )

    assert result is raw_socket
    assert observed["address"] == ("93.184.216.34", 443)
    assert observed["server_hostname"] == "jobs.example.test"
