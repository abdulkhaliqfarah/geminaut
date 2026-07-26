"""Tests for geminaut.protocol \u2014 TOFU trust store and link resolution."""

from __future__ import annotations

import hashlib

import pytest

import geminaut.protocol as protocol
from geminaut.protocol import CertificateChangedError, resolve_link


@pytest.fixture(autouse=True)
def _isolated_trust_store(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "TRUST_STORE_PATH", tmp_path / "known_hosts")


def test_first_connection_is_trusted_and_remembered() -> None:
    cert = b"fake-cert-bytes-1"
    protocol._verify_tofu("example.org:1965", cert)  # should not raise
    stored = protocol._load_trust_store()
    assert stored["example.org:1965"] == hashlib.sha256(cert).hexdigest()


def test_matching_certificate_on_repeat_visit_is_fine() -> None:
    cert = b"fake-cert-bytes-2"
    protocol._verify_tofu("example.org:1965", cert)
    protocol._verify_tofu("example.org:1965", cert)  # should not raise


def test_changed_certificate_raises() -> None:
    protocol._verify_tofu("example.org:1965", b"first-cert")
    with pytest.raises(CertificateChangedError):
        protocol._verify_tofu("example.org:1965", b"different-cert")


def test_different_hosts_are_tracked_independently() -> None:
    protocol._verify_tofu("a.example:1965", b"cert-a")
    protocol._verify_tofu("b.example:1965", b"cert-b")
    stored = protocol._load_trust_store()
    assert stored["a.example:1965"] != stored["b.example:1965"]


def test_resolve_link_handles_relative_and_parent_paths() -> None:
    assert (
        resolve_link("gemini://example.org/dir/page.gmi", "../other.gmi")
        == "gemini://example.org/other.gmi"
    )
    assert (
        resolve_link("gemini://example.org/dir/page.gmi", "sibling.gmi")
        == "gemini://example.org/dir/sibling.gmi"
    )
    assert (
        resolve_link("gemini://example.org/page.gmi", "gemini://other.org/")
        == "gemini://other.org/"
    )
