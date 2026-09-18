import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hybrid AI Options Platform",
  description: "Human-in-the-Loop Cryptocurrency Options Analytics, Risk Management, and Paper Trading Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full antialiased">
      <body className="min-h-full flex flex-col bg-[#0a0e17] text-slate-100">{children}</body>
    </html>
  );
}
