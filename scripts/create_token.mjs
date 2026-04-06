/**
 * Four.meme token creation bridge — called by the Python agent.
 *
 * Usage: node scripts/create_token.mjs '{"name":"TokenName","symbol":"TKN","description":"desc","imageUrl":"https://...","devBuyBnb":0.01}'
 *
 * Uses @fnzero/four-trading-sdk for on-chain operations.
 * The SDK handles TokenManager2 ABI and contract interaction directly.
 */

import { ethers } from "ethers";
import dotenv from "dotenv";
import { readFileSync } from "fs";

dotenv.config();

const PRIVATE_KEY = process.env.PRIVATE_KEY;
const RPC_URL = process.env.BSC_RPC_URL || "https://bsc-dataseed.binance.org";

// TokenManager3 (current) from Four.meme's /v1/public/address
const TOKEN_MANAGER = "0x5c952063c7fc8610ffdb798152d69f0b9550762b";

// Minimal ABI for createToken + events
const TOKEN_MANAGER_ABI = [
  "function createToken(bytes calldata createArg, bytes calldata signature) payable",
  "event TokenCreate(address indexed token, address indexed creator, string name, string symbol)",
];

async function main() {
  const args = JSON.parse(process.argv[2] || "{}");
  const { name, symbol, description, imageUrl, devBuyBnb = 0.01 } = args;

  if (!name || !symbol) {
    console.error(JSON.stringify({ error: "name and symbol required" }));
    process.exit(1);
  }

  const provider = new ethers.JsonRpcProvider(RPC_URL);
  const wallet = new ethers.Wallet(PRIVATE_KEY, provider);
  console.error(`Wallet: ${wallet.address}`);

  // Step 1: Get createArg + signature from Four.meme API
  // First, authenticate
  const httpHeaders = {
    "Content-Type": "application/json",
    "User-Agent": "four-life-agent/1.0.0",
    "Origin": "https://four.meme",
    "Referer": "https://four.meme/",
  };

  // Try to get a nonce and login
  let accessToken = null;
  try {
    const nonceResp = await fetch(
      `https://four.meme/meme-api/v1/public/user/login/nonce?walletAddress=${wallet.address.toLowerCase()}`,
      { headers: httpHeaders }
    );
    if (nonceResp.ok) {
      const nonceData = await nonceResp.json();
      const nonce = nonceData.data;

      const message = `You are sign in Meme ${nonce}`;
      const signature = await wallet.signMessage(message);

      const loginResp = await fetch(
        "https://four.meme/meme-api/v1/public/user/login",
        {
          method: "POST",
          headers: httpHeaders,
          body: JSON.stringify({
            walletAddress: wallet.address.toLowerCase(),
            signature,
            nonce,
            loginType: "ETH",
          }),
        }
      );
      if (loginResp.ok) {
        const loginData = await loginResp.json();
        accessToken = loginData.data?.accessToken;
        console.error("Auth: legacy login succeeded");
      }
    }
  } catch (e) {
    console.error(`Auth: legacy failed - ${e.message}`);
  }

  if (!accessToken) {
    // Try new wallet-direct auth
    try {
      const ts = Date.now().toString();
      const msg = `Welcome to four.meme!\n\nClick to connect your wallet and accept the Terms of Service.\n\nThis request will not trigger a blockchain transaction or cost any gas fees.\n\nWallet address:\n${wallet.address.toLowerCase()}\n\nNonce:\n${ts}`;
      const sig = await wallet.signMessage(msg);

      const signResp = await fetch(
        "https://four.meme/mapi/defi/v3/public/wallet-direct/wallet/address/sign",
        {
          method: "POST",
          headers: { ...httpHeaders },
          body: JSON.stringify({
            address: wallet.address.toLowerCase(),
            signature: sig,
            message: msg,
            timestamp: ts,
          }),
        }
      );
      const signData = await signResp.json();
      if (signData.success || signData.code === "000000") {
        accessToken = signData.data?.token || signData.data?.accessToken;
        console.error("Auth: wallet-direct succeeded");
      } else {
        console.error(`Auth: wallet-direct failed - ${signData.message || signData.code}`);
      }
    } catch (e) {
      console.error(`Auth: wallet-direct error - ${e.message}`);
    }
  }

  if (!accessToken) {
    console.error("Auth: All auth methods failed. Cannot create token via API.");
    console.error("Falling back to monitoring-only mode.");
    console.log(JSON.stringify({ error: "auth_failed", message: "Four.meme auth unavailable" }));
    process.exit(1);
  }

  // Step 2: Upload image (if URL is a local path or data)
  let imgUrl = imageUrl;
  if (!imgUrl) {
    imgUrl = "https://static.four.meme/market/default.png";
  }

  // Step 3: Create token via API
  const authHeaders = {
    ...httpHeaders,
    Authorization: `Bearer ${accessToken}`,
  };

  const createResp = await fetch(
    "https://four.meme/meme-api/v1/private/token/create",
    {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({
        name,
        symbol,
        description: description || name,
        imgUrl,
        raisedTokenSymbol: "BNB",
        raisedAmount: "0",
      }),
    }
  );
  const createData = await createResp.json();

  if (createData.code !== 0 && createData.code !== 200) {
    console.log(JSON.stringify({ error: "create_failed", message: createData.msg, data: createData }));
    process.exit(1);
  }

  const { createArg, signature: serverSig } = createData.data;
  console.error(`Token creation args received`);

  // Step 4: Submit on-chain
  const contract = new ethers.Contract(TOKEN_MANAGER, TOKEN_MANAGER_ABI, wallet);
  const creationFee = ethers.parseEther("0.005");
  const devBuy = ethers.parseEther(String(devBuyBnb));
  const totalValue = creationFee + devBuy;

  console.error(`Submitting on-chain (value: ${ethers.formatEther(totalValue)} BNB)...`);

  const tx = await contract.createToken(createArg, serverSig, { value: totalValue });
  console.error(`Tx sent: ${tx.hash}`);

  const receipt = await tx.wait();
  console.error(`Tx confirmed: ${receipt.hash}`);

  // Find the token address from events
  let tokenAddress = null;
  for (const log of receipt.logs) {
    try {
      const parsed = contract.interface.parseLog(log);
      if (parsed && parsed.name === "TokenCreate") {
        tokenAddress = parsed.args.token;
        break;
      }
    } catch {}
  }

  console.log(
    JSON.stringify({
      success: true,
      txHash: receipt.hash,
      tokenAddress,
      name,
      symbol,
    })
  );
}

main().catch((e) => {
  console.log(JSON.stringify({ error: "exception", message: e.message }));
  process.exit(1);
});
