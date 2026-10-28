"""Fetch public job pages safely and extract fields useful for scam analysis."""

import http.client
import ipaddress
import json
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from html.parser import HTMLParser
from email.message import Message
from urllib.parse import quote, urljoin, urlsplit, urlunsplit


MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
REQUEST_TIMEOUT = (3.05, 8)
DNS_RESOLUTION_TIMEOUT = 5
_DNS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="job-page-dns")
USER_AGENT = "RecruitmentGuardJobScanner/1.0 (+job-posting safety analysis)"
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class JobPageScanError(ValueError):
    """A URL could not be fetched or did not contain a readable job page."""

    def __init__(self, message: str, code: str = "scan_failed") -> None:
        super().__init__(message)
        self.code = code


class JobPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.json_ld: list[str] = []
        self._in_title = False
        self._ignored_depth = 0
        self._json_ld_depth = 0
        self._json_ld_parts: list[str] = []
        self._main_depth = 0
        self._main_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): (value or "").strip() for key, value in attrs}
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            content = values.get("content", "")
            if key and content and key not in self.meta:
                self.meta[key] = content
        if tag == "title":
            self._in_title = True
        if tag in {"main", "article"}:
            self._main_depth += 1
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        if tag == "script" and values.get("type", "").lower() == "application/ld+json":
            self._json_ld_depth = 1
            self._json_ld_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"main", "article"} and self._main_depth:
            self._main_depth -= 1
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
        if tag == "script" and self._json_ld_depth:
            value = "".join(self._json_ld_parts).strip()
            if value:
                self.json_ld.append(value)
            self._json_ld_depth = 0
            self._json_ld_parts = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not value:
            return
        if self._in_title:
            self.title_parts.append(value)
        if self._json_ld_depth:
            self._json_ld_parts.append(data)
        if not self._ignored_depth:
            self.text_parts.append(value)
            if self._main_depth:
                self._main_text.append(value)


def _validate_public_url(url: str) -> tuple[str, set[str]]:
    if len(url) > 2048:
        raise JobPageScanError("The job page URL is too long.", "invalid_url")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise JobPageScanError("The URL is malformed.", "invalid_url") from error

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if scheme not in {"http", "https"}:
        raise JobPageScanError(
            "Only public HTTP and HTTPS job page URLs are supported.",
            "invalid_url",
        )
    if not hostname or parsed.username or parsed.password:
        raise JobPageScanError(
            "Enter a valid public job page URL without credentials.",
            "invalid_url",
        )
    if port is not None and port != (80 if scheme == "http" else 443):
        raise JobPageScanError(
            "Only standard HTTP (80) and HTTPS (443) ports are allowed.",
            "invalid_url",
        )
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        raise JobPageScanError(
            "Local and private network addresses cannot be scanned.",
            "private_address",
        )

    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            future = _DNS_EXECUTOR.submit(
                socket.getaddrinfo,
                hostname,
                port or (443 if scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
            answers = future.result(timeout=DNS_RESOLUTION_TIMEOUT)
        except FutureTimeoutError as error:
            future.cancel()
            raise JobPageScanError(
                "DNS lookup timed out. Try again later.",
                "dns_timeout",
            ) from error
        except socket.gaierror as error:
            if error.errno == socket.EAI_AGAIN:
                raise JobPageScanError(
                    "DNS lookup is temporarily unavailable. Try again later.",
                    "dns_temporary_failure",
                ) from error
            if error.errno == socket.EAI_NONAME:
                raise JobPageScanError(
                    "The hostname does not exist in DNS. Check the URL spelling or domain DNS records.",
                    "hostname_unresolved",
                ) from error
            raise JobPageScanError(
                "DNS lookup failed for the job page hostname.",
                "dns_failure",
            ) from error
        except (socket.timeout, TimeoutError) as error:
            raise JobPageScanError(
                "DNS lookup timed out. Try again later.",
                "dns_timeout",
            ) from error
        except OSError as error:
            raise JobPageScanError(
                "DNS lookup failed while resolving the job page hostname.",
                "dns_failure",
            ) from error
        resolved = {answer[4][0].split("%", 1)[0] for answer in answers}
    else:
        resolved = {str(literal_ip)}

    if not resolved:
        raise JobPageScanError(
            "The job page hostname has no usable addresses.",
            "hostname_unresolved",
        )
    for address in resolved:
        try:
            parsed_ip = ipaddress.ip_address(address)
        except ValueError as error:
            raise JobPageScanError(
                "The job page resolved to an invalid address.",
                "dns_failure",
            ) from error
        if not parsed_ip.is_global:
            raise JobPageScanError(
                "Local and private network addresses cannot be scanned.",
                "private_address",
            )

    normalized = urlunsplit((scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))
    return normalized, resolved


def _normalized_ip(address: str) -> str:
    parsed_ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(parsed_ip, ipaddress.IPv6Address) and parsed_ip.ipv4_mapped:
        return str(parsed_ip.ipv4_mapped)
    return str(parsed_ip)


def _open_pinned_connection(
    address: str,
    port: int,
    scheme: str,
    server_name: str,
) -> socket.socket:
    connection = socket.create_connection((address, port), timeout=REQUEST_TIMEOUT[0])
    if scheme != "https":
        return connection
    try:
        return ssl.create_default_context().wrap_socket(
            connection,
            server_hostname=server_name,
        )
    except (OSError, ssl.SSLError):
        connection.close()
        raise


def _request_public_page(
    url: str,
    allowed_addresses: set[str],
) -> tuple[int, dict[str, str], bytes, str]:
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    scheme = parsed.scheme.lower()
    port = parsed.port or (443 if scheme == "https" else 80)
    normalized_addresses = {_normalized_ip(address) for address in allowed_addresses}
    if not normalized_addresses:
        raise JobPageScanError(
            "The job page hostname has no usable addresses.",
            "hostname_unresolved",
        )

    server_name = hostname
    try:
        server_name = str(ipaddress.ip_address(hostname))
    except ValueError:
        try:
            server_name = hostname.encode("idna").decode("ascii")
        except UnicodeError as error:
            raise JobPageScanError(
                "The job page hostname is invalid.",
                "invalid_url",
            ) from error
    host_header = f"[{server_name}]" if ":" in server_name else server_name
    default_port = 443 if scheme == "https" else 80
    if port != default_port:
        host_header = f"{host_header}:{port}"
    target = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    if parsed.query:
        target += "?" + quote(parsed.query, safe="/?@:!$&'()*+,;=-._~%")

    connection_errors: list[OSError | ssl.SSLError | http.client.HTTPException] = []
    for address in sorted(normalized_addresses):
        connection: socket.socket | None = None
        response: http.client.HTTPResponse | None = None
        try:
            connection = _open_pinned_connection(
                address,
                port,
                scheme,
                server_name,
            )
            peer = _normalized_ip(connection.getpeername()[0])
            if peer not in normalized_addresses:
                raise JobPageScanError(
                    "The page connection resolved to an unexpected address.",
                    "unsafe_address",
                )

            connection.settimeout(REQUEST_TIMEOUT[1])
            request_data = (
                f"GET {target} HTTP/1.1\r\n"
                f"Host: {host_header}\r\n"
                f"User-Agent: {USER_AGENT}\r\n"
                "Accept: text/html,application/xhtml+xml\r\n"
                "Accept-Encoding: identity\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            connection.sendall(request_data)
            response = http.client.HTTPResponse(connection, method="GET")
            response.begin()
            headers = {
                key.lower(): value.strip()
                for key, value in response.getheaders()
            }
            status = response.status

            content_encoding = headers.get("content-encoding", "identity").lower()
            if content_encoding not in {"", "identity"}:
                raise JobPageScanError(
                    "The page uses an unsupported compressed response.",
                    "unsupported_response",
                )
            content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if status not in REDIRECT_STATUSES:
                if status < 200 or status >= 300:
                    raise JobPageScanError(
                        f"The job page returned HTTP {status}.",
                        "upstream_http_error",
                    )
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    raise JobPageScanError(
                        "The URL does not serve an HTML job page.",
                        "unsupported_response",
                    )

            declared_length = headers.get("content-length")
            if declared_length:
                try:
                    length = int(declared_length)
                except ValueError as error:
                    raise JobPageScanError(
                        "The job page returned an invalid content length.",
                        "invalid_response",
                    ) from error
                if length > MAX_PAGE_BYTES:
                    raise JobPageScanError(
                        "The job page is larger than the 2 MB scan limit.",
                        "response_too_large",
                    )

            chunks: list[bytes] = []
            total = 0
            if status not in REDIRECT_STATUSES:
                while True:
                    chunk = response.read(min(16 * 1024, MAX_PAGE_BYTES + 1 - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_PAGE_BYTES:
                        raise JobPageScanError(
                            "The job page is larger than the 2 MB scan limit.",
                            "response_too_large",
                        )
                    chunks.append(chunk)

            content_type_header = Message()
            content_type_header["content-type"] = headers.get("content-type", "")
            encoding = content_type_header.get_content_charset() or "utf-8"
            return status, headers, b"".join(chunks), encoding
        except JobPageScanError:
            raise
        except (OSError, ssl.SSLError, http.client.HTTPException) as error:
            connection_errors.append(error)
        finally:
            if response is not None:
                response.close()
            if connection is not None:
                connection.close()

    certificate_error = next(
        (
            error
            for error in connection_errors
            if isinstance(error, ssl.SSLCertVerificationError)
        ),
        None,
    )
    if certificate_error is not None:
        raise JobPageScanError(
            "The job page TLS certificate could not be verified.",
            "tls_verification_failed",
        ) from certificate_error
    tls_error = next(
        (error for error in connection_errors if isinstance(error, ssl.SSLError)),
        None,
    )
    if tls_error is not None:
        raise JobPageScanError(
            "The job page TLS connection failed.",
            "tls_connection_failed",
        ) from tls_error
    timeout_error = next(
        (
            error
            for error in connection_errors
            if isinstance(error, (socket.timeout, TimeoutError))
        ),
        None,
    )
    if timeout_error is not None:
        raise JobPageScanError(
            "The job page connection timed out.",
            "connection_timeout",
        ) from timeout_error
    protocol_error = next(
        (
            error
            for error in connection_errors
            if isinstance(error, http.client.HTTPException)
        ),
        None,
    )
    if protocol_error is not None:
        raise JobPageScanError(
            "The job page returned an invalid HTTP response.",
            "invalid_response",
        ) from protocol_error
    raise JobPageScanError(
        "The job page could not be reached. Check the server or network and try again.",
        "connection_failed",
    ) from (connection_errors[-1] if connection_errors else None)


def _read_html(url: str) -> tuple[str, bytes, str]:
    current_url = url
    for redirect_number in range(MAX_REDIRECTS + 1):
        safe_url, allowed_addresses = _validate_public_url(current_url)
        status, headers, body, encoding = _request_public_page(safe_url, allowed_addresses)
        if status in REDIRECT_STATUSES:
            location = headers.get("location")
            if not location:
                raise JobPageScanError(
                    "The job page returned a redirect without a destination.",
                    "invalid_redirect",
                )
            if redirect_number == MAX_REDIRECTS:
                raise JobPageScanError(
                    "The job page redirected too many times.",
                    "too_many_redirects",
                )
            current_url = urljoin(safe_url, location)
            continue
        return safe_url, body, encoding

    raise JobPageScanError(
        "The job page could not be reached.",
        "connection_failed",
    )


def _plain_text(value: object) -> str:
    if isinstance(value, str):
        parser = JobPageParser()
        parser.feed(value)
        text = " ".join(parser.text_parts) if "<" in value else value
        return " ".join(text.split())[:20000]
    if isinstance(value, dict):
        if "address" in value and isinstance(value["address"], dict):
            address = value["address"]
            parts = [
                _plain_text(address.get(key, ""))
                for key in (
                    "streetAddress",
                    "addressLocality",
                    "addressRegion",
                    "postalCode",
                    "addressCountry",
                )
            ]
            return ", ".join(part for part in parts if part)
        for key in (
            "name",
            "value",
            "address",
            "addressLocality",
            "addressRegion",
            "addressCountry",
            "streetAddress",
        ):
            if key in value:
                text = _plain_text(value[key])
                if text:
                    return text
        return ""
    if isinstance(value, list):
        return ", ".join(filter(None, (_plain_text(item) for item in value)))[:20000]
    return ""


def _job_posting_nodes(value: object) -> list[dict[str, object]]:
    if isinstance(value, list):
        return [node for item in value for node in _job_posting_nodes(item)]
    if not isinstance(value, dict):
        return []
    type_value = value.get("@type", [])
    types = type_value if isinstance(type_value, list) else [type_value]
    found = [value] if "jobposting" in {str(item).lower() for item in types} else []
    graph = value.get("@graph")
    if isinstance(graph, (list, dict)):
        found.extend(_job_posting_nodes(graph))
    return found


def extract_job_details(html: str, scanned_url: str) -> dict[str, str]:
    parser = JobPageParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as error:
        raise JobPageScanError(
            "The job page HTML could not be parsed.",
            "invalid_response",
        ) from error

    structured_jobs: list[dict[str, object]] = []
    for script in parser.json_ld:
        try:
            structured_jobs.extend(_job_posting_nodes(json.loads(script)))
        except (json.JSONDecodeError, TypeError):
            continue

    structured = structured_jobs[0] if structured_jobs else {}
    organization = structured.get("hiringOrganization", {})
    description = _plain_text(structured.get("description", ""))
    if not description:
        description = " ".join(parser._main_text or parser.text_parts)[:20000]
    title = _plain_text(structured.get("title", "")) or parser.meta.get("og:title") or " ".join(parser.title_parts)
    company = _plain_text(organization) or parser.meta.get("og:site_name", "") or parser.meta.get("author", "")
    company_website = ""
    if isinstance(organization, dict):
        company_website = _plain_text(organization.get("url", organization.get("sameAs", "")))
    location_value = structured.get("jobLocation", structured.get("jobLocationType", ""))
    location = _plain_text(location_value)
    requirements = " ".join(
        filter(
            None,
            (
                _plain_text(structured.get("qualifications", "")),
                _plain_text(structured.get("experienceRequirements", "")),
                _plain_text(structured.get("educationRequirements", "")),
            ),
        )
    )
    benefits = _plain_text(structured.get("jobBenefits", ""))
    if not description:
        description = parser.meta.get("description", "") or parser.meta.get("og:description", "")
    if not description:
        raise JobPageScanError(
            "No readable job description was found on this page.",
            "job_details_not_found",
        )
    return {
        "title": title[:500],
        "location": location[:1000],
        "company_profile": company[:20000],
        "company_website": company_website[:2000],
        "description": description[:20000],
        "requirements": requirements[:20000],
        "benefits": benefits[:20000],
        "scanned_url": scanned_url,
    }


def scan_job_page(url: str) -> dict[str, str]:
    normalized_url, _ = _validate_public_url(url.strip())
    final_url, content, encoding = _read_html(normalized_url)
    try:
        html = content.decode(encoding, errors="replace")
    except LookupError:
        html = content.decode("utf-8", errors="replace")
    return extract_job_details(html, final_url)
