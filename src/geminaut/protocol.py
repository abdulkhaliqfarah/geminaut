"""Gemini protocol client: TLS transport, TOFU certificate pinning, and requests."""

from __future__ import annotations

import hashlib
import socket
import ssl
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

# `urllib.parse.urljoin` only resolves relative references (../foo, foo.gmi, etc.)
# for schemes it knows about. "gemini" isn't one of them by default, so relative
# links in gemtext would otherwise be returned unresolved. Registering it here is
# the standard workaround for teaching urljoin about a custom URI scheme.
if "gemini" not in urllib.parse.uses_relative:
    urllib.parse.uses_relative.append("gemini")
if "gemini" not in urllib.parse.uses_netloc:
    urllib.parse.uses_netloc.append("gemini")

DEFAULT_PORT = 1965
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MiB guard against unbounded reads
REQUEST_TIMEOUT = 15.0

TRUST_STORE_PATH = Path.home() / ".config" / "geminaut" / "known_hosts"


class GeminiError(RuntimeError):
    """Raised for any failure talking to a Gemini server."""


class CertificateChangedError(GeminiError):
    """Raised when a host's certificate fingerprint no longer matches what we trusted."""

    def __init__(self, host: str, expected: str, got: str) -> None:
        super().__init__(
            f"Certificate for {host} changed (expected {expected[:16]}\u2026, got "
            f"{got[:16]}\u2026). This could mean the site rotated its certificate, or "
            "that you're being intercepted. Refusing to connect; delete the entry in "
            f"{TRUST_STORE_PATH} if you're sure this is expected."
        )
        self.host = host
        self.expected = expected
        self.got = got


@dataclass
class GeminiResponse:
    """A parsed Gemini response: status code, meta line, and raw body."""

    status: int
    meta: str
    body: bytes

    @property
    def is_success(self) -> bool:
        return 20 <= self.status < 30

    @property
    def is_redirect(self) -> bool:
        return 30 <= self.status < 40

    @property
    def is_input_request(self) -> bool:
        return 10 <= self.status < 20

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def _load_trust_store() -> dict[str, str]:
    if not TRUST_STORE_PATH.exists():
        return {}
    entries: dict[str, str] = {}
    for line in TRUST_STORE_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        host, _, fingerprint = line.partition(" ")
        if host and fingerprint:
            entries[host] = fingerprint
    return entries


def _remember(host: str, fingerprint: str) -> None:
    TRUST_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    entries = _load_trust_store()
    entries[host] = fingerprint
    lines = [f"{h} {fp}" for h, fp in sorted(entries.items())]
    TRUST_STORE_PATH.write_text("\n".join(lines) + "\n")


def _verify_tofu(host: str, der_cert: bytes, *, trust_on_first_use: bool = True) -> None:
    """Trust-On-First-Use: pin a host's certificate fingerprint like SSH host keys."""
    fingerprint = hashlib.sha256(der_cert).hexdigest()
    known = _load_trust_store()
    existing = known.get(host)
    if existing is None:
        if trust_on_first_use:
            _remember(host, fingerprint)
        return
    if existing != fingerprint:
        raise CertificateChangedError(host, existing, fingerprint)


def resolve_link(base_url: str, target: str) -> str:
    """Resolve a link target (from a gemtext `=>` line or redirect) against the current URL."""
    return urljoin(base_url, target)


def request(
    url: str, *, timeout: float = REQUEST_TIMEOUT, trust_on_first_use: bool = True
) -> GeminiResponse:
    """Perform a single Gemini request and return the parsed response."""
    parts = urlsplit(url)
    if parts.scheme != "gemini":
        raise GeminiError(f"Not a gemini:// URL: {url}")
    host = parts.hostname
    if not host:
        raise GeminiError(f"URL has no host: {url}")
    port = parts.port or DEFAULT_PORT

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with socket.create_connection((host, port), timeout=timeout) as raw_sock:
            with context.wrap_socket(raw_sock, server_hostname=host) as tls_sock:
                der_cert = tls_sock.getpeercert(binary_form=True)
                if der_cert:
                    _verify_tofu(
                        f"{host}:{port}", der_cert, trust_on_first_use=trust_on_first_use
                    )

                tls_sock.sendall(f"{url}\r\n".encode())

                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = tls_sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise GeminiError(
                            f"Response from {host} exceeded {MAX_RESPONSE_BYTES} bytes"
                        )
    except TimeoutError as exc:
        raise GeminiError(f"Timed out connecting to {host}:{port}") from exc
    except OSError as exc:
        raise GeminiError(f"Could not connect to {host}:{port}: {exc}") from exc

    raw = b"".join(chunks)
    header, _, body = raw.partition(b"\r\n")
    header_text = header.decode("utf-8", errors="replace")
    if len(header_text) < 2 or not header_text[:2].isdigit():
        raise GeminiError(f"Malformed response header from {host}: {header_text!r}")

    status = int(header_text[:2])
    meta = header_text[3:] if len(header_text) > 3 else ""
    return GeminiResponse(status=status, meta=meta, body=body)
