import type { Metadata } from "next";
import GlobalQuickCreate from "@/components/GlobalQuickCreate";
import "./globals.css";

export const metadata: Metadata = {
  title: "MyBuddy",
  description: "Your private, self-hosted AI companion.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <GlobalQuickCreate />
      </body>
    </html>
  );
}
