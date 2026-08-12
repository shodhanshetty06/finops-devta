"use client";

import { Cloud, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Tooltip } from "@/components/ui/tooltip";
import { NAV_SECTIONS } from "@/lib/nav-items";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";

const COLLAPSE_KEY = "finops:sidebar-collapsed";

function isActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppSidebar({ variant = "desktop", onNavigate }: { variant?: "desktop" | "mobile"; onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    // Restores collapse state from localStorage - external-system state
    // unknown during the initial render, so this deliberately syncs one
    // tick after mount rather than risk an SSR/client mismatch.
    if (variant !== "desktop") return;
    const stored = window.localStorage.getItem(COLLAPSE_KEY);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stored === "1") setCollapsed(true);
  }, [variant]);

  function toggleCollapsed() {
    setCollapsed((c) => {
      const next = !c;
      window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  }

  const showLabels = variant === "mobile" || !collapsed;

  return (
    <div
      className={cn(
        "flex h-full flex-col bg-sidebar transition-[width] duration-150",
        variant === "desktop" && (collapsed ? "w-[68px]" : "w-64"),
        variant === "mobile" && "w-full",
      )}
    >
      <div className={cn("flex h-14 shrink-0 items-center border-b border-sidebar-border px-4", !showLabels && "justify-center px-0")}>
        <Link href="/dashboard" className="flex items-center gap-2 font-semibold text-sidebar-foreground" onClick={onNavigate}>
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Cloud className="h-4 w-4" />
          </span>
          {showLabels && <span className="text-[15px] tracking-tight">FinOps</span>}
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-2.5 py-4" aria-label="Primary">
        <div className="flex flex-col gap-5">
          {NAV_SECTIONS.map((section) => {
            const items = section.items.filter((item) => !item.requiresRole || item.requiresRole === user?.role);
            if (items.length === 0) return null;
            return (
              <div key={section.label} className="flex flex-col gap-0.5">
                {showLabels && (
                  <p className="px-2.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {section.label}
                  </p>
                )}
                {items.map((item) => {
                  const active = isActive(pathname, item.href);
                  const link = (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13.5px] font-medium transition-colors",
                        !showLabels && "justify-center px-0 py-2.5",
                        active
                          ? "bg-sidebar-active text-primary-700 dark:text-primary-300"
                          : "text-sidebar-foreground hover:bg-muted",
                      )}
                    >
                      <item.icon className={cn("h-[18px] w-[18px] shrink-0", active ? "text-primary-600 dark:text-primary-400" : "text-muted-foreground group-hover:text-foreground")} />
                      {showLabels && <span className="truncate">{item.label}</span>}
                    </Link>
                  );
                  return showLabels ? (
                    link
                  ) : (
                    <Tooltip key={item.href} content={item.label} side="right">
                      {link}
                    </Tooltip>
                  );
                })}
              </div>
            );
          })}
        </div>
      </nav>

      {variant === "desktop" && (
        <div className="shrink-0 border-t border-sidebar-border p-2.5">
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
              !showLabels && "justify-center px-0",
            )}
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            {showLabels && <span>Collapse</span>}
          </button>
        </div>
      )}
    </div>
  );
}
