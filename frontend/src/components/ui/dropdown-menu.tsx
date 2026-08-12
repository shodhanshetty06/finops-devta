"use client";

import { createContext, useContext, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";
import { useClickOutside, useEscapeKey } from "@/hooks/use-dismiss";

interface DropdownMenuContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  triggerRef: React.RefObject<HTMLButtonElement | null>;
}

const DropdownMenuContext = createContext<DropdownMenuContextValue | null>(null);

function useDropdownMenu() {
  const ctx = useContext(DropdownMenuContext);
  if (!ctx) throw new Error("DropdownMenu.* must be used within <DropdownMenu>");
  return ctx;
}

export function DropdownMenu({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  return (
    <DropdownMenuContext.Provider value={{ open, setOpen, triggerRef }}>
      <div className="relative inline-block">{children}</div>
    </DropdownMenuContext.Provider>
  );
}

export function DropdownMenuTrigger({ children, className }: { children: ReactNode; className?: string }) {
  const { open, setOpen, triggerRef } = useDropdownMenu();
  return (
    <button
      ref={triggerRef}
      type="button"
      aria-haspopup="menu"
      aria-expanded={open}
      onClick={() => setOpen(!open)}
      className={cn("focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md", className)}
    >
      {children}
    </button>
  );
}

export function DropdownMenuContent({
  children,
  align = "end",
  className,
}: {
  children: ReactNode;
  align?: "start" | "end";
  className?: string;
}) {
  const { open, setOpen, triggerRef } = useDropdownMenu();
  const contentRef = useRef<HTMLDivElement>(null);
  useClickOutside([contentRef, triggerRef], open, () => setOpen(false));
  useEscapeKey(open, () => setOpen(false));

  if (!open) return null;

  return (
    <div
      ref={contentRef}
      role="menu"
      className={cn(
        "absolute z-40 mt-1.5 min-w-[12rem] rounded-lg border border-border bg-surface-raised p-1 shadow-popover animate-slide-up",
        align === "end" ? "right-0" : "left-0",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function DropdownMenuItem({
  children,
  onSelect,
  className,
  destructive,
  disabled,
}: {
  children: ReactNode;
  onSelect?: () => void;
  className?: string;
  destructive?: boolean;
  disabled?: boolean;
}) {
  const { setOpen } = useDropdownMenu();
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={() => {
        onSelect?.();
        setOpen(false);
      }}
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
        destructive ? "text-destructive hover:bg-error-50 dark:hover:bg-error-900/30" : "text-foreground hover:bg-muted",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function DropdownMenuLabel({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("px-2.5 py-1.5 text-xs font-medium text-muted-foreground", className)}>{children}</div>;
}

export function DropdownMenuSeparator() {
  return <div className="my-1 h-px bg-border" />;
}
