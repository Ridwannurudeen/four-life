"""Webhook signature utilities.

The FOUR-LIFE webhook dispatcher signs every delivery with:

    X-FourLife-Signature: t=<unix_ts>,v1=<hex_hmac_sha256>

where the signed payload is f"{t}.{raw_body}". This module provides
the matching verifier (and a signer, handy for tests)."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Union

__all__ = ["sign_payload", "verify_webhook_signature"]


def sign_payload(
    *,
    secret: str,
    body: Union[str, bytes],
    timestamp: int,
) -> str:
    """Compute the value for the `X-FourLife-Signature` header.

    Args:
        secret: The shared webhook secret returned by POST /api/webhooks.
        body: The raw request body, exactly as it will be sent.
        timestamp: Unix-seconds timestamp to include in the signed payload.

    Returns:
        The signature header value, e.g. ``"t=1776380000,v1=abcd..."``.
    """
    body_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
    signed = f"{int(timestamp)}.".encode("utf-8") + body_bytes
    mac = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={int(timestamp)},v1={mac}"


def verify_webhook_signature(
    *,
    secret: str,
    body: Union[str, bytes],
    signature_header: str,
    tolerance_seconds: int = 300,
    now: Union[int, None] = None,
) -> bool:
    """Verify a FOUR-LIFE webhook signature header.

    Args:
        secret: The shared webhook secret stored when the subscription was created.
        body: The raw request body (bytes or str) — must match exactly what was received.
        signature_header: The value of the ``X-FourLife-Signature`` header.
        tolerance_seconds: Reject signatures where ``|now - t|`` exceeds this window.
            Defaults to 300 seconds (5 minutes), matching the server-side tolerance.
        now: Current unix timestamp, used for replay protection. Auto-filled if omitted.

    Returns:
        True iff the signature is well-formed, verifies against the secret, and is
        within the tolerance window.
    """
    if not signature_header:
        return False

    parts: dict[str, str] = {}
    for seg in signature_header.split(","):
        if "=" not in seg:
            continue
        k, v = seg.split("=", 1)
        parts[k.strip()] = v.strip()

    t = parts.get("t")
    v1 = parts.get("v1")
    if not t or not v1:
        return False
    try:
        t_int = int(t)
    except ValueError:
        return False

    now_ts = int(now) if now is not None else int(time.time())
    if abs(now_ts - t_int) > int(tolerance_seconds):
        return False

    body_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
    signed = f"{t_int}.".encode("utf-8") + body_bytes
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)
