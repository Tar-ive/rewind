import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import ClientShell from "@/components/ClientShell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Rewind — The Intelligent Life Scheduler",
  description:
    "AI-powered life operating system that detects disruptions, reschedules your day, and executes busywork autonomously.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-zinc-950 text-white`}
      >
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-hidden flex flex-col">
            <ClientShell>{children}</ClientShell>
          </main>
        </div>
      </body>
    </html>
  );
}
