import type { Metadata } from "next";

import { RouteScrollReset } from "@/components/route-scroll-reset";

import "./globals.css";

export const metadata: Metadata = {
  title: "MeaningSync — Shared meaning for service agreements",
  description: "Make sure both sides mean the same thing.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <RouteScrollReset />
        {children}
      </body>
    </html>
  );
}
