import type { Priority } from "@/types/schedule";

export const PRIORITY_CONFIG: Record<
  Priority,
  { label: string; color: string; bg: string; border: string }
> = {
  P0: {
    label: "Urgent",
    color: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
  },
  P1: {
    label: "Important",
    color: "text-orange-400",
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
  },
  P2: {
    label: "Normal",
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  P3: {
    label: "Background",
    color: "text-zinc-400",
    bg: "bg-zinc-500/10",
    border: "border-zinc-500/30",
  },
};

export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
