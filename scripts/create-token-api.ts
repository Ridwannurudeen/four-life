#!/usr/bin/env node
/**
 * Four.meme API-side token creation: auth → upload image → create token → output JSON.
 *
 * Called by create-token-instant.ts. Outputs JSON to stdout:
 *   { "createArg": "0x...", "signature": "0x...", "creationFeeWei": "..." }
 *
 * Usage:
 *   npx tsx create-token-api.ts --image=./logo.png --name=MyToken --short-name=MTK --desc="desc" --label=AI
 *
 * Env: PRIVATE_KEY (required), BSC_RPC_URL (optional)
 */

import { createWalletClient, http } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { bsc } from 'viem/chains';
import fs from 'node:fs';
import path from 'node:path';

const API_BASE = 'https://four.meme/meme-api/v1';

function getOpt(key: string, defaultValue = ''): string {
  const prefix = `--${key}=`;
  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith(prefix)) return arg.slice(prefix.length);
  }
  return defaultValue;
}

async function apiPost(path: string, body: unknown, token?: string): Promise<unknown> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Origin': 'https://four.meme',
    'Referer': 'https://four.meme/',
    'User-Agent': 'four-life-agent/1.0.0',
  };
  if (token) headers['meme-web-access'] = token;

  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`API ${path}: ${resp.status} ${resp.statusText}`);
  const data = await resp.json() as { code: string; data: unknown; msg?: string };
  if (String(data.code) !== "0" && String(data.code) !== "000000") {
    throw new Error(`API ${path}: ${data.msg || JSON.stringify(data)}`);
  }
  return data.data;
}

async function apiGet(path: string): Promise<unknown> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Origin': 'https://four.meme',
      'Referer': 'https://four.meme/',
    },
  });
  if (!resp.ok) throw new Error(`API ${path}: ${resp.status}`);
  const data = await resp.json() as { code: string; data: unknown };
  if (String(data.code) !== "0" && String(data.code) !== "000000") {
    throw new Error(`API ${path}: ${JSON.stringify(data)}`);
  }
  return data.data;
}

async function uploadImage(imagePath: string, token: string): Promise<string> {
  const fileBuffer = fs.readFileSync(imagePath);
  const fileName = path.basename(imagePath);
  const blob = new Blob([fileBuffer], { type: 'image/png' });

  const form = new FormData();
  form.append('file', blob, fileName);

  const resp = await fetch(`${API_BASE}/private/token/upload`, {
    method: 'POST',
    headers: {
      'meme-web-access': token,
      'Origin': 'https://four.meme',
      'Referer': 'https://four.meme/',
    },
    body: form,
  });
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);
  const data = await resp.json() as { code: string; data: string };
  if (String(data.code) !== "0" && String(data.code) !== "000000") {
    throw new Error(`Upload failed: ${JSON.stringify(data)}`);
  }
  return data.data;
}

function toHex(s: string): string {
  if (s.startsWith('0x')) return s;
  // Assume base64
  const buf = Buffer.from(s, 'base64');
  return '0x' + buf.toString('hex');
}

async function main() {
  const privateKey = process.env.PRIVATE_KEY;
  if (!privateKey) { console.error('Set PRIVATE_KEY'); process.exit(1); }

  const imagePath = getOpt('image');
  const name = getOpt('name');
  const shortName = getOpt('short-name');
  const desc = getOpt('desc');
  const label = getOpt('label', 'AI');
  const webUrl = getOpt('web-url');
  const preSale = getOpt('pre-sale', '0');

  if (!name || !shortName) {
    console.error('Required: --name=X --short-name=X');
    process.exit(1);
  }

  const pk = (privateKey.startsWith('0x') ? privateKey : `0x${privateKey}`) as `0x${string}`;
  const account = privateKeyToAccount(pk);
  const address = account.address;

  // Step 1: Auth — get nonce
  const nonce = await apiPost('/private/user/nonce/generate', {
    accountAddress: address,
    verifyType: 'LOGIN',
    networkCode: 'BSC',
  }) as string;

  // Step 2: Sign nonce
  const message = `You are sign in Meme ${nonce}`;
  const rpcUrl = process.env.BSC_RPC_URL || 'https://bsc-dataseed.binance.org';
  const client = createWalletClient({ account, chain: bsc, transport: http(rpcUrl) });
  const signature = await client.signMessage({ message });

  // Step 3: Login
  const accessToken = await apiPost('/private/user/login/dex', {
    region: 'WEB',
    langType: 'EN',
    loginIp: '',
    inviteCode: '',
    verifyInfo: {
      address,
      networkCode: 'BSC',
      signature,
      verifyType: 'LOGIN',
    },
    walletName: 'MetaMask',
  }) as string;

  // Step 4: Upload image (if provided)
  let imgUrl = '';
  if (imagePath && fs.existsSync(imagePath)) {
    imgUrl = await uploadImage(imagePath, accessToken);
  }

  // Step 5: Get BNB config
  const configs = await apiGet('/public/config') as Array<{
    symbol: string; totalAmount: number; totalBAmount: number; saleRate: number;
  }>;
  const bnbConfig = configs.find((c) => c.symbol === 'BNB') || configs[0];

  // Step 6: Create token via API
  const body: Record<string, unknown> = {
    name,
    shortName,
    desc: desc || name,
    totalSupply: Number(bnbConfig.totalAmount) || 1_000_000_000,
    raisedAmount: Number(bnbConfig.totalBAmount) || 24,
    saleRate: Number(bnbConfig.saleRate) || 0.8,
    reserveRate: 0,
    imgUrl,
    raisedToken: bnbConfig,
    launchTime: Date.now() + 30_000,
    funGroup: false,
    label,
    lpTradingFee: 0.0025,
    preSale,
    clickFun: false,
    symbol: 'BNB',
    dexType: 'PANCAKE_SWAP',
    rushMode: false,
    onlyMPC: false,
    feePlan: false,
  };
  if (webUrl) body.webUrl = webUrl;

  const result = await apiPost('/private/token/create', body, accessToken) as {
    createArg: string;
    signature: string;
    creationFee?: string;
  };

  // Convert base64 to hex if needed
  const createArg = toHex(result.createArg);
  const sig = toHex(result.signature);

  // Output JSON for create-token-instant.ts
  console.log(JSON.stringify({
    createArg,
    signature: sig,
    creationFeeWei: result.creationFee || '0',
  }));
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
