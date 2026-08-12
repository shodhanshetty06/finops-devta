"use client";

import { useQuery } from "@tanstack/react-query";
import { CornerDownLeft, FolderKanban, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import { useEffect, useMemo, useRef, useState } from "react";

import { projectsApi } from "@/lib/api-client";
import { ALL_NAV_ITEMS } from "@/lib/nav-items";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { useEscapeKey, useScrollLock } from "@/hooks/use-dismiss";

/** Global "search everywhere" palette - Cmd+K / Ctrl+K from anywhere in the
 * app, mounted once in the app shell. Searches nav destinations and the
 * user's own projects (fetched lazily, only once the palette opens). */
export function CommandMenu() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const { isAuthenticated, user } = useAuth();

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  useEscapeKey(open, () => setOpen(false));
  useScrollLock(open);

  useEffect(() => {
    // Synchronizes with two external systems on open: resets the query/
    // selection state and moves DOM focus into the input - a real effect,
    // not something derivable at render time.
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setQuery("");
      setActiveIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
    enabled: open && isAuthenticated,
    staleTime: 30_000,
  });

  const navResults = useMemo(() => {
    const items = user?.role === "admin" ? ALL_NAV_ITEMS : ALL_NAV_ITEMS.filter((i) => i.requiresRole !== "admin");
    if (!query.trim()) return items;
    const q = query.toLowerCase();
    return items.filter((i) => i.label.toLowerCase().includes(q) || i.description.toLowerCase().includes(q));
  }, [query, user]);

  const projectResults = useMemo(() => {
    const projects = projectsQuery.data ?? [];
    if (!query.trim()) return projects.slice(0, 5);
    const q = query.toLowerCase();
    return projects.filter((p) => p.name.toLowerCase().includes(q)).slice(0, 8);
  }, [query, projectsQuery.data]);

  type Result = { key: string; label: string; sublabel: string; href: string; icon: React.ReactNode };
  const results: Result[] = [
    ...navResults.map((i) => ({
      key: `nav-${i.href}`,
      label: i.label,
      sublabel: i.description,
      href: i.href,
      icon: <i.icon className="h-4 w-4" />,
    })),
    ...projectResults.map((p) => ({
      key: `project-${p.id}`,
      label: p.name,
      sublabel: p.latest_version ? `v${p.latest_version}` : "No estimates yet",
      href: `/projects/${p.id}`,
      icon: <FolderKanban className="h-4 w-4" />,
    })),
  ];

  function navigate(href: string) {
    setOpen(false);
    router.push(href);
  }

  function handleQueryChange(value: string) {
    setQuery(value);
    setActiveIndex(0);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && results[activeIndex]) {
      e.preventDefault();
      navigate(results[activeIndex].href);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="hidden items-center gap-2 rounded-md border border-border-strong bg-surface px-3 py-1.5 text-sm text-muted-foreground shadow-xs transition-colors hover:border-primary-300 hover:text-foreground sm:flex"
        aria-label="Search everywhere"
      >
        <Search className="h-3.5 w-3.5" />
        <span>Search...</span>
        <kbd className="ml-6 rounded border border-border-strong bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
          {typeof navigator !== "undefined" && navigator.platform.includes("Mac") ? "⌘K" : "Ctrl K"}
        </kbd>
      </button>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Search everywhere"
        className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground sm:hidden"
      >
        <Search className="h-4 w-4" />
      </button>

      {open &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]" role="presentation">
            <div className="fixed inset-0 bg-slate-950/50 backdrop-blur-[2px] animate-fade-in" onClick={() => setOpen(false)} aria-hidden="true" />
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Search everywhere"
              className="relative z-10 flex w-full max-w-xl flex-col overflow-hidden rounded-xl border border-border bg-surface-raised shadow-lg animate-slide-up"
            >
              <div className="flex items-center gap-2.5 border-b border-border px-4 py-3">
                <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => handleQueryChange(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Search pages, projects..."
                  aria-label="Search"
                  className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                />
                <kbd className="rounded border border-border-strong px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">Esc</kbd>
              </div>
              <div className="max-h-80 overflow-y-auto p-2">
                {results.length === 0 && (
                  <p className="px-3 py-8 text-center text-sm text-muted-foreground">No results for &ldquo;{query}&rdquo;</p>
                )}
                {results.map((r, i) => (
                  <button
                    key={r.key}
                    type="button"
                    onClick={() => navigate(r.href)}
                    onMouseEnter={() => setActiveIndex(i)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                      i === activeIndex ? "bg-accent text-accent-foreground" : "text-foreground",
                    )}
                  >
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                      {r.icon}
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate font-medium">{r.label}</span>
                      <span className="truncate text-xs text-muted-foreground">{r.sublabel}</span>
                    </span>
                    {i === activeIndex && <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
                  </button>
                ))}
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
