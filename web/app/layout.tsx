import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
  weight: ["300", "400", "500", "600", "700", "800", "900"],
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "FOUR-LIFE | The trust layer for Four.meme launches",
  description:
    "Deterministic trust grading, autonomous protection, and signed webhooks for every Four.meme token. Built on BNB Chain.",
  metadataBase: new URL("https://four-life.gudman.xyz"),
  openGraph: {
    title: "FOUR-LIFE — The trust layer for Four.meme",
    description:
      "Deterministic badges. Protection mode. Signed webhooks. Python + TypeScript SDKs. Built on BNB Chain.",
    url: "https://four-life.gudman.xyz",
    siteName: "FOUR-LIFE",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "FOUR-LIFE — The trust layer for Four.meme",
    description:
      "Deterministic badges. Protection mode. Signed webhooks. Python + TypeScript SDKs.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`h-full antialiased ${inter.variable} ${jetbrains.variable}`}>
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
