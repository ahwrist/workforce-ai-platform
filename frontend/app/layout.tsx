import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "WorkforceAI Platform",
  description: "AI adoption upskilling and consulting hub",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
