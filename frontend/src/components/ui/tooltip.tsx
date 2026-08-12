"use client";

import { useId, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Self-contained hover/focus tooltip - no provider needed. Shows after a
 * short delay to avoid flashing on quick mouse passes, matches the
 * "subtle, fast" motion guidance (150ms fade, no spring/bounce). */
export function Tooltip({
  content,
  children,
  side = "top",
  delay = 300,
}: {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  delay?: number;
}) {
  const [visible, setVisible] = useState(false);
  const [timer, setTimer] = useState<ReturnType<typeof setTimeout> | null>(null);
  const id = useId();

  function show() {
    setTimer(setTimeout(() => setVisible(true), delay));
  }
  function hide() {
    if (timer) clearTimeout(timer);
    setVisible(false);
  }

  const sideClasses: Record<string, string> = {
    top: "bottom-full left-1/2 mb-2 -translate-x-1/2",
    bottom: "top-full left-1/2 mt-2 -translate-x-1/2",
    left: "right-full top-1/2 mr-2 -translate-y-1/2",
    right: "left-full top-1/2 ml-2 -translate-y-1/2",
  };

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {typeof children === "string" ? (
        <span aria-describedby={visible ? id : undefined}>{children}</span>
      ) : (
        children
      )}
      {visible && (
        <span
          id={id}
          role="tooltip"
          className={cn(
            "pointer-events-none absolute z-50 whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-white shadow-lg animate-fade-in dark:bg-slate-100 dark:text-slate-900",
            sideClasses[side],
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}
