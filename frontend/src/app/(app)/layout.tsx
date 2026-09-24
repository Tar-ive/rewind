import Sidebar from "@/components/Sidebar";
import ClientShell from "@/components/ClientShell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 text-white">
      <Sidebar />
      <main className="flex-1 overflow-hidden flex flex-col">
        <ClientShell>{children}</ClientShell>
      </main>
    </div>
  );
}
