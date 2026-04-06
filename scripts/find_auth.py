"""Find the auth adapter in Four.meme's JS bundle."""
import re

js = open("/tmp/app.js").read()

patterns = {
    "createAuth": r"createAuth[a-zA-Z]*\(.{0,500}",
    "adapter getNonce": r"adapter.{0,50}getNonce",
    "fetchNonce": r"fetchNonce.{0,300}",
    "meme-api nonce": r"meme-api.{0,30}nonce",
    "meme-api login": r"meme-api.{0,30}login",
    "meme-api auth": r"meme-api.{0,30}auth",
    "/login": r"/v\d/public[/a-z]*login.{0,200}",
    "accessToken set": r"accessToken.{0,200}",
    "user_token set": r"(set|save|store).{0,30}user_token.{0,200}",
    "meme-web-access": r"meme-web-access.{0,200}",
    "authentication adapter": r"authentication.{0,100}adapter.{0,300}",
    "SiweMessage": r"SiweMessage.{0,300}",
    "siwe": r"siwe.{0,300}",
}

for name, pattern in patterns.items():
    matches = re.findall(pattern, js, re.IGNORECASE)
    if matches:
        print(f"\n=== {name} ({len(matches)} matches) ===")
        for m in matches[:2]:
            print(m[:400])
            print("---")
