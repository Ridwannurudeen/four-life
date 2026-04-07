import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FOUR-LIFE | Autonomous Meme Token Lifecycle Agent",
  description: "The first AI agent that doesn't just launch tokens — it raises them. Built for Four.meme on BNB Chain.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
