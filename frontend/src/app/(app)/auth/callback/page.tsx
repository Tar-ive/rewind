"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function AuthCallbackPage() {
  const [canClose, setCanClose] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      window.close();
      // If still open after 500ms, show manual link
      setTimeout(() => setCanClose(true), 500);
    }, 1500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="flex h-full items-center justify-center flex-col gap-4">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-500/10 border border-green-500/30">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
      </div>
      <h1 className="text-lg font-semibold text-white">Connected Successfully</h1>
      <p className="text-sm text-zinc-500">
        {canClose
          ? "You can close this tab and return to Rewind."
          : "Closing this tab..."}
      </p>
      {canClose && (
        <Link
          href="/integrations"
          className="text-sm text-blue-400 hover:text-blue-300 hover:underline transition-colors"
        >
          Return to Integrations
        </Link>
      )}
    </div>
  );
}
