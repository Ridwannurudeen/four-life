"""Tests for the webhook signature helpers."""

import pytest

from four_life import sign_payload, verify_webhook_signature


class TestSignPayload:
    def test_signature_is_stable(self):
        sig1 = sign_payload(secret="whsec_x", body='{"a":1}', timestamp=1_000)
        sig2 = sign_payload(secret="whsec_x", body='{"a":1}', timestamp=1_000)
        assert sig1 == sig2
        assert sig1.startswith("t=1000,v1=")

    def test_bytes_and_str_bodies_match(self):
        sig_str = sign_payload(secret="whsec_x", body="hello", timestamp=42)
        sig_bytes = sign_payload(secret="whsec_x", body=b"hello", timestamp=42)
        assert sig_str == sig_bytes


class TestVerifyWebhookSignature:
    def test_roundtrip_ok(self):
        secret = "whsec_abc"
        body = '{"type":"badge.tier_changed"}'
        sig = sign_payload(secret=secret, body=body, timestamp=1_000)
        assert verify_webhook_signature(
            secret=secret, body=body, signature_header=sig, now=1_000,
        ) is True

    def test_tampered_body_fails(self):
        secret = "whsec_abc"
        sig = sign_payload(secret=secret, body='{"a":1}', timestamp=1_000)
        assert verify_webhook_signature(
            secret=secret, body='{"a":2}', signature_header=sig, now=1_000,
        ) is False

    def test_wrong_secret_fails(self):
        sig = sign_payload(secret="whsec_real", body="hi", timestamp=1_000)
        assert verify_webhook_signature(
            secret="whsec_wrong", body="hi", signature_header=sig, now=1_000,
        ) is False

    def test_expired_timestamp_fails(self):
        sig = sign_payload(secret="whsec_x", body="hi", timestamp=1_000)
        assert verify_webhook_signature(
            secret="whsec_x", body="hi", signature_header=sig, now=1_000 + 400,
            tolerance_seconds=300,
        ) is False

    def test_future_timestamp_fails(self):
        sig = sign_payload(secret="whsec_x", body="hi", timestamp=1_500)
        assert verify_webhook_signature(
            secret="whsec_x", body="hi", signature_header=sig, now=1_000,
            tolerance_seconds=300,
        ) is False

    def test_malformed_header_returns_false(self):
        assert verify_webhook_signature(
            secret="whsec_x", body="hi", signature_header="garbage", now=1_000,
        ) is False

    def test_missing_header_returns_false(self):
        assert verify_webhook_signature(
            secret="whsec_x", body="hi", signature_header="", now=1_000,
        ) is False

    def test_missing_t_component_returns_false(self):
        assert verify_webhook_signature(
            secret="whsec_x", body="hi",
            signature_header="v1=deadbeef", now=1_000,
        ) is False

    def test_bytes_body_accepted(self):
        secret = "whsec_x"
        body_bytes = b'{"a":1}'
        sig = sign_payload(secret=secret, body=body_bytes, timestamp=1_000)
        assert verify_webhook_signature(
            secret=secret, body=body_bytes, signature_header=sig, now=1_000,
        ) is True
