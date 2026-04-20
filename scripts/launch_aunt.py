"""One-shot launcher for AuntieCoin (approved concept from /api/agent/think).

Generates the artwork via DGrid, invokes scripts/create-token-instant.ts, parses
the token address from the output, and POSTs to /api/agent/track so the
lifecycle engine picks it up immediately.
"""
import asyncio
import os
import subprocess
import sys
import json
import re
import time
import tempfile
from pathlib import Path

sys.path.insert(0, '/opt/four-life')
from agent.brain.llm import get_llm

CONCEPT = {
    'name': 'AuntieCoin',
    'symbol': 'AUNT',
    'description': "Tired of your portfolio looking like leftover dim sum? Auntie's here to scold you into financial success. HODL harder, invest wisely.",
    'label': 'Meme',
    'personality': 'Sharp-tongued, financially shrewd Asian auntie archetype',
    'narrative': 'Underrepresented East/Southeast Asian Cultural Memes',
    'lore': "Legend says Auntie emerged from the steam of a thousand bamboo steamers, clutching a ledger filled with ancient trading wisdom. She scolds diamond hands and paper hands alike.",
}

IMAGE_PROMPT = (
    'A cartoon portrait of a stern but loving Asian auntie character with a halo of financial charts and trading graphs around her head. '
    'She holds a bowl of dim sum in one hand and a laptop showing crypto candles in the other. '
    'Playful meme-coin aesthetic, bold colors, clean vector style, transparent-style background. '
    'No text. Distinctive, recognizable character suitable for a BNB Chain meme token logo.'
)

async def main():
    print('[1/4] Generating artwork via DGrid...')
    llm = get_llm()
    img_bytes = await llm.generate_image(IMAGE_PROMPT)
    img_path = tempfile.mktemp(suffix='.png')
    Path(img_path).write_bytes(img_bytes)
    print(f'  image: {img_path} ({len(img_bytes)} bytes)')
    print(f'  last_provider: {llm.last_provider} · last_model: {llm.last_model}')

    print('[2/4] Invoking create-token-instant.ts...')
    env = {**os.environ, 'PRIVATE_KEY': os.environ.get('PRIVATE_KEY', '')}
    # Load .env into this process env
    for line in Path('/opt/four-life/.env').read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

    cmd = [
        'npx', 'tsx', 'scripts/create-token-instant.ts',
        f'--image={img_path}',
        f'--name={CONCEPT["name"]}',
        f'--short-name={CONCEPT["symbol"]}',
        f'--desc={CONCEPT["description"][:200]}',
        f'--label={CONCEPT["label"]}',
    ]
    print('  cmd:', ' '.join(cmd))
    t0 = time.time()
    proc = subprocess.run(cmd, cwd='/opt/four-life', env=env, capture_output=True, text=True, timeout=180)
    elapsed = time.time() - t0
    print(f'  exit: {proc.returncode} · elapsed: {elapsed:.1f}s')
    print('  stdout:', proc.stdout[-2000:])
    if proc.returncode != 0:
        print('  stderr:', proc.stderr[-2000:])
        sys.exit(1)

    print('[3/4] Parsing token address + tx hash...')
    # Typical output includes createToken tx hash and subsequently the deployed token address
    text = proc.stdout + proc.stderr
    tx_hash_match = re.search(r'txHash[:\s]*0x([a-fA-F0-9]{64})', text)
    addr_match = re.search(r'token[A-Za-z_]*[:\s]*0x([a-fA-F0-9]{40})', text)
    tx_hash = ('0x' + tx_hash_match.group(1)) if tx_hash_match else None
    addr = ('0x' + addr_match.group(1)) if addr_match else None
    print(f'  tx_hash: {tx_hash}')
    print(f'  token_address: {addr}')
    if not addr:
        print('  WARN: no address found in output — see stdout above')
        sys.exit(2)

    print('[4/4] Registering token with lifecycle engine...')
    import urllib.request
    req_body = json.dumps({
        'token_address': addr,
        'name': CONCEPT['name'],
        'symbol': CONCEPT['symbol'],
        'quote_asset': 'BNB',
        'concept': CONCEPT,
    }).encode()
    req = urllib.request.Request(
        'http://127.0.0.1:8030/api/agent/track',
        data=req_body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {env.get("API_SECRET","")}',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print('  track_response:', resp.read().decode())

    print('\nDONE:')
    print(f'  token_address: {addr}')
    print(f'  tx: https://bscscan.com/tx/{tx_hash}')
    print(f'  four.meme: https://four.meme/token/{addr}')

asyncio.run(main())
