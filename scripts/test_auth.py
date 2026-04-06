"""Test Four.meme auth endpoints to find working combination."""

import asyncio
import time
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eth_account import Account
from eth_account.messages import encode_defunct
import httpx
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.environ["PRIVATE_KEY"]
acct = Account.from_key(PRIVATE_KEY)
addr = acct.address.lower()
print(f"Wallet: {addr}")


async def try_auth():
    ts = str(int(time.time() * 1000))

    # Different sign messages Four.meme might use
    messages = [
        f"Welcome to four.meme!\n\nThis request will not trigger a blockchain transaction or cost any gas fees.\n\nAuthentication nonce: {ts}",
        f"You are sign in Meme {ts}",
        f"{ts}",
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        # Test 1: Try the /mapi/defi/ sign endpoint
        print("\n=== Testing /mapi/defi/v3 sign endpoint ===")
        for i, msg in enumerate(messages):
            signable = encode_defunct(text=msg)
            signed = acct.sign_message(signable)
            sig = signed.signature.hex()
            if not sig.startswith("0x"):
                sig = "0x" + sig

            payloads = [
                {"address": addr, "signature": sig, "message": msg, "timestamp": ts},
                {"walletAddress": addr, "signature": sig, "message": msg, "timestamp": ts},
                {"address": addr, "signature": sig, "timestamp": ts},
            ]

            for payload in payloads:
                try:
                    resp = await client.post(
                        "https://four.meme/mapi/defi/v3/public/wallet-direct/wallet/address/sign",
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "Origin": "https://four.meme",
                            "Referer": "https://four.meme/",
                        },
                    )
                    data = resp.json()
                    code = data.get("code", "")
                    success = data.get("success", False)
                    msg_resp = data.get("message", "")
                    print(f"  msg[{i}] keys={list(payload.keys())}: code={code} success={success} msg={msg_resp}")
                    if success or code == "000000":
                        print(f"  >>> SUCCESS! Data: {json.dumps(data, indent=2)}")
                        return data
                except Exception as e:
                    print(f"  msg[{i}]: error {e}")

            # Also try GET
            try:
                params = {"address": addr, "signature": sig, "message": msg, "timestamp": ts}
                resp = await client.get(
                    "https://four.meme/mapi/defi/v3/public/wallet-direct/wallet/address/sign",
                    params=params,
                    headers={"Origin": "https://four.meme", "Referer": "https://four.meme/"},
                )
                data = resp.json()
                print(f"  GET msg[{i}]: code={data.get('code', '')} success={data.get('success', '')} msg={data.get('message', '')}")
                if data.get("success") or data.get("code") == "000000":
                    print(f"  >>> SUCCESS! Data: {json.dumps(data, indent=2)}")
                    return data
            except Exception as e:
                print(f"  GET msg[{i}]: error {e}")

        # Test 2: Try the old /meme-api nonce endpoint with different paths
        print("\n=== Testing alternative /meme-api paths ===")
        alt_paths = [
            "/v1/public/user/login/nonce",
            "/v2/public/user/login/nonce",
            "/v1/public/user/nonce",
            "/v1/public/address",
        ]
        for path in alt_paths:
            try:
                resp = await client.get(
                    f"https://four.meme/meme-api{path}",
                    params={"walletAddress": addr},
                )
                print(f"  GET {path}: {resp.status_code} {resp.text[:100]}")
            except Exception as e:
                print(f"  GET {path}: error {e}")

            try:
                resp = await client.post(
                    f"https://four.meme/meme-api{path}",
                    json={"walletAddress": addr},
                    headers={"Content-Type": "application/json"},
                )
                print(f"  POST {path}: {resp.status_code} {resp.text[:100]}")
            except Exception as e:
                print(f"  POST {path}: error {e}")

        # Test 3: Check /v1/public/address
        print("\n=== Testing /v1/public/address ===")
        try:
            resp = await client.post(
                "https://four.meme/meme-api/v1/public/address",
                json={"walletAddress": addr},
                headers={
                    "Content-Type": "application/json",
                    "Origin": "https://four.meme",
                    "Referer": "https://four.meme/",
                },
            )
            print(f"  POST: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"  error: {e}")

    return None


asyncio.run(try_auth())
