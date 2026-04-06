"""Search ALL JS chunks for the auth adapter implementation."""
import re
import subprocess
import sys

# Get all JS chunk URLs
result = subprocess.run(
    ["curl", "-s", "https://four.meme"],
    capture_output=True, text=True
)
chunks = re.findall(r'/_next/static/chunks/[a-zA-Z0-9/_.-]+\.js', result.stdout)
chunks = list(set(chunks))
print(f"Found {len(chunks)} chunks")

for chunk_url in chunks:
    url = f"https://four.meme{chunk_url}"
    result = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
    js = result.stdout

    # Search for the adapter definition - it will have getNonce as a method
    for pattern in [
        r'getNonce:\s*async\s*\(\)',
        r'getNonce:\s*function',
        r'getNonce\s*\(\s*\)\s*\{',
        r'verify\s*\(\s*\{message',
        r'createMessage\s*\(\s*\{address',
    ]:
        matches = re.findall(pattern + r'.{0,300}', js)
        if matches:
            print(f"\n=== {chunk_url} — {pattern} ===")
            for m in matches[:2]:
                print(m[:400])
                print("---")
