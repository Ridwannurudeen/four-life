"""Generate a printable PDF of the FOUR-LIFE 90-second demo script.

Writes to C:/Users/HP/Music/FOUR-LIFE-Demo-Script.pdf using reportlab.
Dark-on-light layout so it prints cleanly on any paper.
"""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable,
)
from reportlab.platypus.flowables import Flowable

OUT = Path(r"C:\Users\HP\Music\FOUR-LIFE-Demo-Script.pdf")
OUT.parent.mkdir(parents=True, exist_ok=True)

CYAN = HexColor("#00a8cf")
GREEN = HexColor("#3fbf1a")
INK = HexColor("#111419")
MUTED = HexColor("#475569")
FAINT = HexColor("#8a94a3")
LINE = HexColor("#e2e8f0")
PANEL = HexColor("#f7f9fb")

styles = getSampleStyleSheet()


def p(text: str, style: str = "Body") -> Paragraph:
    return Paragraph(text, styles[style])


styles.add(ParagraphStyle(name="Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=15, textColor=INK, spaceAfter=4))
styles.add(ParagraphStyle(name="BodyTight", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=14, textColor=INK, spaceAfter=2))
styles.add(ParagraphStyle(name="TitleBig", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=26, leading=32, textColor=INK, spaceAfter=4))
styles.add(ParagraphStyle(name="Subtitle", parent=styles["BodyText"], fontName="Helvetica", fontSize=11.5, leading=16, textColor=MUTED, spaceAfter=10))
styles.add(ParagraphStyle(name="Beat", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=INK, spaceBefore=14, spaceAfter=2))
styles.add(ParagraphStyle(name="BeatTime", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=CYAN, spaceAfter=4))
styles.add(ParagraphStyle(name="Kicker", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=GREEN, spaceAfter=2))
styles.add(ParagraphStyle(name="H3", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=INK, spaceBefore=10, spaceAfter=3))
styles.add(ParagraphStyle(name="VoiceOver", parent=styles["BodyText"], fontName="Helvetica-Oblique", fontSize=11, leading=16, textColor=INK, leftIndent=10, spaceBefore=2, spaceAfter=6))
styles.add(ParagraphStyle(name="Mono", parent=styles["Code"], fontName="Courier", fontSize=9, leading=12, textColor=INK, spaceAfter=3))
styles.add(ParagraphStyle(name="Check", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, leading=14, textColor=INK, leftIndent=16, spaceAfter=1))
styles.add(ParagraphStyle(name="SmallMuted", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=12, textColor=MUTED, spaceAfter=1))


def hr():
    return HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=8, spaceAfter=8)


def voiceover_box(text: str) -> Table:
    t = Table([[Paragraph(f'<i>"{text}"</i>', styles["VoiceOver"])]],
              colWidths=[16 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("LINEBEFORE", (0, 0), (0, -1), 3, CYAN),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def beat(num: int, time: str, title: str, voiceover: str, actions: list[str], key_phrase: str) -> list:
    out = [
        Paragraph(f"BEAT {num} · {time}", styles["BeatTime"]),
        Paragraph(title, styles["Beat"]),
        voiceover_box(voiceover),
        Spacer(1, 2),
        Paragraph("<b>On-screen actions:</b>", styles["BodyTight"]),
    ]
    for a in actions:
        out.append(Paragraph(f"&#8226;&nbsp; {a}", styles["Check"]))
    out.append(Spacer(1, 4))
    out.append(Paragraph(f'<b>Key phrase to hit aloud:</b> &ldquo;{key_phrase}&rdquo;', styles["SmallMuted"]))
    return out


doc = SimpleDocTemplate(
    str(OUT),
    pagesize=A4,
    leftMargin=2.2 * cm,
    rightMargin=2.2 * cm,
    topMargin=1.8 * cm,
    bottomMargin=1.8 * cm,
    title="FOUR-LIFE Demo Script",
    author="FOUR-LIFE",
)

flow: list = []

# ── Cover ─────────────────────────────────────────────────────────────
flow.append(Paragraph("FOUR-LIFE", styles["Kicker"]))
flow.append(Paragraph("90-second Demo Script", styles["TitleBig"]))
flow.append(Paragraph(
    "Four.meme AI Sprint &middot; BNB Chain &middot; Submission deadline Apr 22 23:59 UTC",
    styles["Subtitle"],
))
flow.append(hr())

# ── One-sentence pitch ────────────────────────────────────────────────
flow.append(Paragraph("The pitch (memorise this)", styles["H3"]))
flow.append(Paragraph(
    "FOUR-LIFE is the autonomous lifecycle agent for Four.meme meme tokens. "
    "It grades every token with pure on-chain rules (zero LLM in the trust path) "
    "and Merkle-commits every operational LLM decision to BNB Chain.",
    styles["Body"],
))

# ── Prep ─────────────────────────────────────────────────────────────
flow.append(Paragraph("Before you hit record", styles["H3"]))
flow.append(Paragraph("Open these tabs in this exact order:", styles["BodyTight"]))
prep = [
    "1. <b>https://four-life.gudman.xyz/</b> &mdash; the landing page",
    "2. <b>https://four-life.gudman.xyz/radar</b> &mdash; the live radar",
    "3. <b>https://four-life.gudman.xyz/proof</b> &mdash; the outcome ledger",
    "4. <b>https://four.meme/en/token/0x568bf737887053ffa8aa4e82d8859ca4a9a14444</b> &mdash; $AUNT",
    "5. <b>FOUR-LIFE Chrome extension</b> &mdash; reloaded at v1.5.3, pinned to toolbar",
]
for line in prep:
    flow.append(Paragraph(line, styles["Check"]))
flow.append(Spacer(1, 6))
flow.append(Paragraph(
    "<b>Test token throughout:</b> $AUNT &mdash; <font face='Courier'>0x568bf737887053ffa8aa4e82d8859ca4a9a14444</font>",
    styles["SmallMuted"],
))
flow.append(Paragraph(
    "<b>Chrome zoom:</b> 125% so click targets are legible on compressed video. "
    "<b>Recorder:</b> 1080p / 30fps / on-board mic test once before you go live.",
    styles["SmallMuted"],
))
flow.append(hr())

# ── Beat 1 ─────────────────────────────────────────────────────────────
flow.extend(beat(
    1, "0:00 &rarr; 0:20",
    "The Hook &mdash; landing page",
    "Four.meme launches fifty tokens a day. Only one point three four percent ever graduate. The other ninety-eight percent die silently inside seventy-two hours &mdash; from whale rugs, stalled curves, coordinated sells. FOUR-LIFE is Phase 4: the autonomous lifecycle agent that keeps them alive.",
    [
        "Point at the eyebrow pill: <b>LIVE ON BNB CHAIN &middot; 88 GRADED &middot; 8 CERTIFIED &middot; AGENT ID 20</b>",
        "Scroll past the 1.34% headline",
        "Briefly reveal the <b>Architecture diagram</b> section &mdash; Token &rarr; Agent loop &rarr; Deterministic Grade + Attested LLM &rarr; 5 consumer surfaces",
    ],
    "Phase 4.",
))
flow.append(hr())

# ── Beat 2 ─────────────────────────────────────────────────────────────
flow.extend(beat(
    2, "0:20 &rarr; 0:45",
    "The Grade &mdash; /radar",
    "Every Four.meme token shows up here, graded in real time. Eight live-monitored tokens are Certified &mdash; that means full on-chain rule trace, no LLM in the trust path. Fifty-two are Radar Estimates from public ranking &mdash; labelled differently, never confused.",
    [
        "Point at the <b>tier breakdown strip</b>: 8 At Risk &middot; 52 Observed",
        "Click the first Certified row (AUNT or DOUJIAO)",
        "Drawer opens &rarr; point at the <b>rule trace cards</b> (whale_extreme, sell_pressure, curve_stalled, whale_cluster)",
        "Hover the <b>&#8505; icon</b> on any rule &rarr; plain-english tooltip appears",
    ],
    "Deterministic rule trace &mdash; anyone can reproduce the grade from raw on-chain data.",
))
flow.append(PageBreak())

# ── Beat 3 ─────────────────────────────────────────────────────────────
flow.extend(beat(
    3, "0:45 &rarr; 1:15",
    "The Proof &mdash; /proof",
    "Here's the agent's record. Thirty-two launches deployed, five graduated &mdash; that's fifteen point six percent, more than eleven times the platform average. Every operational LLM call the agent makes &mdash; narrative picks, hedge decisions &mdash; is hash-chained, and published roots are anchored on BNB Chain. Five thousand twenty-four DGrid calls and thirteen thousand six hundred eighty-nine MYX decisions are covered by the latest roots. Eight transactions, all verifiable on BscScan.",
    [
        "Point at <b>Section 0 &ldquo;The ledger&rdquo;</b> &mdash; the 5 big stat numbers light up live",
        "Click any of the 4 link cards (agent wallet / ERC-8004 / DGrid root / MYX root) &rarr; BscScan opens &rarr; close the tab",
        "Scroll to <b>Section 5 &ldquo;Graduated tokens&rdquo;</b> &mdash; 4 real tokens that reached 100% curve",
    ],
    "Provable on-chain. Not a promise &mdash; a transaction.",
))
flow.append(hr())

# ── Beat 4 ─────────────────────────────────────────────────────────────
flow.extend(beat(
    4, "1:15 &rarr; 1:30",
    "The Firewall &mdash; four.meme / $AUNT",
    "And it's not just a dashboard. Watch this.",
    [
        "Point at the <b>red pulsing pill</b> in the top-right &mdash; FOUR-LIFE &middot; At Risk",
        "Click the pill &rarr; deep panel slides in from the right",
        "Briefly pan down the panel: <b>health ring &middot; rule trace &middot; contract safety &middot; creator reputation &middot; snapshot sparkline &middot; on-chain attestation</b>",
        "Click the <b>Swap &uarr;</b> button &rarr; <b>red block modal appears</b>",
        "Point at the quoted evidence lines + the <b>Cancel / Override anyway</b> buttons",
    ],
    "Grade, shield, attest. FOUR-LIFE &mdash; Phase 4 for every Four.meme launch.",
))
flow.append(Spacer(1, 8))
flow.append(Paragraph(
    "<b>Closing line:</b> &ldquo;Try it: four-life dot gudman dot xyz.&rdquo;",
    styles["Body"],
))
flow.append(hr())

# ── Fallback moments ─────────────────────────────────────────────────
flow.append(Paragraph("Fallback demo moments (if time allows)", styles["H3"]))
fallbacks = [
    "<b>Right-click context menu:</b> highlight any 0x address anywhere, right-click &rarr; &ldquo;Grade with FOUR-LIFE&rdquo; &rarr; a new tab opens with the rule trace. Proves the extension works beyond the 4 injected sites.",
    "<b>Keyboard shortcuts:</b> press <font face='Courier'>F</font> to expand, <font face='Courier'>P</font> to pop into a full tab, <font face='Courier'>W</font> to subscribe for Chrome notifications.",
    "<b>Popup dashboard:</b> click the toolbar icon &rarr; live agent state, top radar with curve-progress bars, last 5 agent actions.",
]
for f in fallbacks:
    flow.append(Paragraph(f"&bull; {f}", styles["Check"]))

# ── Do-not-say list ──────────────────────────────────────────────────
flow.append(Paragraph("Do-not-say list (truth boundaries)", styles["H3"]))
flow.append(Paragraph(
    "<b>Do NOT</b> say &ldquo;fully autonomous MYX execution&rdquo; &mdash; execution is signal-only; the broker gate is contract-blocked upstream. Say <b>&ldquo;decision-attestation depth&rdquo;</b>.",
    styles["BodyTight"],
))
flow.append(Paragraph(
    "<b>Do NOT</b> call a <font face='Courier'>radar_estimate</font> badge &ldquo;Certified&rdquo; &mdash; the extension, modal, and notifications all discriminate. Mirror that on camera.",
    styles["BodyTight"],
))
flow.append(Paragraph(
    "<b>Do NOT</b> claim the 8 tracked tokens have graduated &mdash; they're at_risk/partial_history. The 5 graduations come from historical launches, shown on /proof.",
    styles["BodyTight"],
))

# ── Recording checklist ─────────────────────────────────────────────
flow.append(Paragraph("Recording checklist", styles["H3"]))
checks = [
    "All 5 tabs open in order",
    "Chrome at 125% zoom",
    "Extension reloaded &rarr; confirm v1.5.3 via devtools: <font face='Courier'>document.getElementById('four-life-certified-host').dataset.flVersion</font>",
    "Screen recorder set to 1080p 30fps",
    "Microphone test &mdash; one take, 90 seconds max",
    "After recording: set <font face='Courier'>NEXT_PUBLIC_DEMO_VIDEO_URL</font> on the VPS, <font face='Courier'>npm run build</font> &rarr; the DemoVideo slot on the landing page embeds it automatically",
]
for c in checks:
    flow.append(Paragraph(f"&#9744;&nbsp; {c}", styles["Check"]))

flow.append(Spacer(1, 12))
flow.append(HRFlowable(width="100%", thickness=0.6, color=LINE))
flow.append(Paragraph(
    "<font color='#8a94a3'>FOUR-LIFE &middot; Four.meme AI Sprint &middot; BNB Chain &middot; ERC-8004 Agent #20 &middot; four-life.gudman.xyz</font>",
    styles["SmallMuted"],
))

doc.build(flow)
print(f"PDF written: {OUT}  ({OUT.stat().st_size:,} bytes)")
