"use client";

import VoiceAgent from "@/components/VoiceAgent";

export default function ClientShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <VoiceAgent />
    </>
  );
}
