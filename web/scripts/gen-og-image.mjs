// Generate a 1200x630 OG image for FOUR-LIFE. Runs at build time (or
// on demand) via `node scripts/gen-og-image.mjs`. Output lives in
// public/og-home.png so Next.js serves it as a static asset and the
// <meta property="og:image"> tag can point to /og-home.png.
//
// We build the image as an SVG first (text placement + gradients are
// trivial in SVG) and rasterize via sharp. Fonts inside SVG fall back
// to the browser's system sans, which is fine for OG previews because
// platforms screenshot or rasterize the image server-side before
// embedding it in a card.

import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import sharp from "sharp";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const OUT_PATH = resolve(__dirname, "..", "public", "og-home.png");

const W = 1200;
const H = 630;

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#050509"/>
      <stop offset="50%" stop-color="#0b0b0e"/>
      <stop offset="100%" stop-color="#0a120f"/>
    </linearGradient>
    <radialGradient id="glow-1" cx="0.15" cy="0.25" r="0.55">
      <stop offset="0%" stop-color="#6cff32" stop-opacity="0.22"/>
      <stop offset="100%" stop-color="#6cff32" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glow-2" cx="0.85" cy="0.8" r="0.6">
      <stop offset="0%" stop-color="#00d4ff" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#00d4ff" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#00d4ff"/>
      <stop offset="100%" stop-color="#6cff32"/>
    </linearGradient>
    <linearGradient id="text-accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#6cff32"/>
      <stop offset="100%" stop-color="#00d4ff"/>
    </linearGradient>
  </defs>

  <rect width="${W}" height="${H}" fill="url(#bg)"/>
  <rect width="${W}" height="${H}" fill="url(#glow-1)"/>
  <rect width="${W}" height="${H}" fill="url(#glow-2)"/>

  <!-- Subtle grid pattern so the background doesn't read as flat dark -->
  <g stroke="rgba(255,255,255,0.04)" stroke-width="1">
    ${Array.from({ length: 8 }, (_, i) => `<line x1="0" y1="${(H / 8) * (i + 1)}" x2="${W}" y2="${(H / 8) * (i + 1)}"/>`).join("")}
  </g>

  <!-- Eyebrow: live dot + label -->
  <g transform="translate(80, 88)">
    <circle cx="6" cy="8" r="5" fill="#6cff32"/>
    <circle cx="6" cy="8" r="9" fill="none" stroke="#6cff32" stroke-width="1" opacity="0.5"/>
    <text x="24" y="14" font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
          font-size="18" font-weight="700" letter-spacing="3" fill="#6cff32">
      LIVE · BNB CHAIN · ERC-8004 AGENT #20
    </text>
  </g>

  <!-- Brand wordmark -->
  <g transform="translate(80, 155)">
    <text font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
          font-size="28" font-weight="800" letter-spacing="8" fill="rgba(255,255,255,0.45)">
      FOUR-LIFE
    </text>
  </g>

  <!-- Headline — the 1.34% hook -->
  <g transform="translate(80, 230)">
    <text font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
          font-size="68" font-weight="800" fill="#ffffff">
      <tspan>Only </tspan>
      <tspan fill="url(#text-accent)">1.34%</tspan>
      <tspan> of Four.meme</tspan>
    </text>
    <text y="78" font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
          font-size="68" font-weight="800" fill="#ffffff">
      tokens graduate.
    </text>
    <text y="156" font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
          font-size="40" font-weight="500" fill="rgba(255,255,255,0.7)">
      FOUR-LIFE is Phase 4.
    </text>
  </g>

  <!-- Three-chip stat strip -->
  <g transform="translate(80, 480)">
    ${[
      ["1,573", "DGRID CALLS", "#00d4ff"],
      ["518", "MYX DECISIONS", "#6cff32"],
      ["5 / 32", "GRADUATIONS · 15.6%", "#a855f7"],
    ].map(([v, k, color], i) => `
      <g transform="translate(${i * 360}, 0)">
        <rect width="340" height="90" rx="14" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>
        <rect width="3" height="90" rx="1.5" fill="${color}"/>
        <text x="22" y="44" font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
              font-size="34" font-weight="800" fill="#ffffff" letter-spacing="-0.5">${v}</text>
        <text x="22" y="72" font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
              font-size="13" font-weight="700" letter-spacing="2.5" fill="rgba(255,255,255,0.5)">${k}</text>
      </g>
    `).join("")}
  </g>

  <!-- URL footer -->
  <g transform="translate(80, 600)">
    <rect x="-2" y="-16" width="4" height="4" rx="2" fill="url(#accent)"/>
    <text x="12" y="-4" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
          font-size="18" font-weight="600" fill="rgba(255,255,255,0.55)">
      four-life.gudman.xyz
    </text>
  </g>

  <!-- Right-side accent panel -->
  <g opacity="0.85">
    <rect x="${W - 4}" y="0" width="4" height="${H}" fill="url(#accent)"/>
  </g>
</svg>`;

const buf = await sharp(Buffer.from(svg), { density: 200 })
  .resize(W, H, { fit: "contain" })
  .png({ quality: 95 })
  .toBuffer();

writeFileSync(OUT_PATH, buf);
console.log(`Wrote ${OUT_PATH} (${buf.length.toLocaleString()} bytes)`);
