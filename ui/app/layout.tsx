import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "ChronoTrace",
  description:
    "Repairs concurrency-induced flaky asyncio tests by proving which ordering caused them.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-border">
          <nav className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-4" aria-label="Main">
            <Link href="/" className="font-mono text-sm text-accent">
              ChronoTrace
            </Link>
            <Link href="/" className="text-sm text-muted hover:text-text">
              Incidents
            </Link>
            <Link href="/eval" className="text-sm text-muted hover:text-text">
              Results
            </Link>
          </nav>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
