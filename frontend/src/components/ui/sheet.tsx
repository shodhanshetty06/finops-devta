"use client";

import { X } from "lucide-react";
import { createPortal } from "react-dom";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";
import { useEscapeKey, useScrollLock } from "@/hooks/use-dismiss";

export interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  side?: "left" | "right";
  children: React.ReactNode;
}

/** Side-sliding drawer, portaled to `document.body`. Used for the mobile
 * sidebar nav and any "more detail without leaving the page" panel. */
export function Sheet({ open, onOpenChange, side = "right", children }: SheetProps) {
  const [mounted, setMounted] = useState(false);
  // createPortal needs document.body, which doesn't exist during SSR - the
  // standard "detect we're on the client" pattern.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMounted(true), []);
  useEscapeKey(open, () => onOpenChange(false));
  useScrollLock(open);

  if (!mounted || !open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex" role="presentation">
      <div
        className="fixed inset-0 bg-slate-950/50 backdrop-blur-[2px] animate-fade-in"
        onClick={() => onOpenChange(false)}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "relative z-10 flex h-full w-full max-w-xs flex-col overflow-hidden border-border bg-surface shadow-lg animate-slide-in-right",
          side === "right" ? "ml-auto border-l" : "mr-auto border-r",
        )}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}

export function SheetHeader({ className, children, onClose, ...props }: React.HTMLAttributes<HTMLDivElement> & { onClose?: () => void }) {
  return (
    <div className={cn("flex items-center justify-between gap-4 border-b border-border p-4", className)} {...props}>
      <div className="flex flex-col gap-0.5">{children}</div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export function SheetTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-base font-semibold text-foreground", className)} {...props} />;
}

export function SheetBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex-1 overflow-y-auto", className)} {...props} />;
}
