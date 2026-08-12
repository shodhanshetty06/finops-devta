"use client";

import { useState } from "react";

import { AiAssistant } from "@/components/ai-assistant";
import { AppSidebar } from "@/components/app-sidebar";
import { AppTopbar } from "@/components/app-topbar";
import { Sheet, SheetBody } from "@/components/ui/sheet";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <aside className="hidden shrink-0 border-r border-sidebar-border lg:block">
        <AppSidebar />
      </aside>

      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen} side="left">
        <SheetBody className="p-0">
          <AppSidebar variant="mobile" onNavigate={() => setMobileNavOpen(false)} />
        </SheetBody>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar onOpenMobileNav={() => setMobileNavOpen(true)} />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</div>
        </main>
      </div>

      <AiAssistant />
    </div>
  );
}
