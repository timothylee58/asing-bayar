import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bayar.lah — Split duit, no awkward lah.",
  description: "Gamified group payment tracker for Malaysian group culture.",
  openGraph: {
    title: "Bayar.lah",
    description: "Split duit, no awkward lah.",
    siteName: "Bayar.lah",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full flex flex-col antialiased">{children}</body>
    </html>
  );
}
