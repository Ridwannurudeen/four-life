"""Python SDK for the FOUR-LIFE Certified trust layer.

Quick start:

    from four_life import FourLife

    fl = FourLife()
    badge = fl.get_badge("0xabc...")
    print(badge["badge"]["tier"])   # "graduation_watch"

    for entry in fl.get_graduation_radar(limit=20)["radar"]:
        print(entry["symbol"], entry["confidence_score"])

Async variant:

    from four_life import AsyncFourLife
    import asyncio

    async def main():
        async with AsyncFourLife() as fl:
            badge = await fl.get_badge("0xabc...")

    asyncio.run(main())

Webhooks:

    from four_life import verify_webhook_signature

    ok = verify_webhook_signature(
        secret=my_secret,
        body=raw_request_body,
        signature_header=request.headers["X-FourLife-Signature"],
    )
"""

from ._client import (
    AsyncFourLife,
    FourLife,
    FourLifeError,
    DEFAULT_API_BASE,
    SDK_VERSION,
)
from ._webhooks import sign_payload, verify_webhook_signature

__all__ = [
    "AsyncFourLife",
    "FourLife",
    "FourLifeError",
    "DEFAULT_API_BASE",
    "SDK_VERSION",
    "sign_payload",
    "verify_webhook_signature",
]
