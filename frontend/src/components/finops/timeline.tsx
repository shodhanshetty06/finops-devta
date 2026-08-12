import type { LucideIcon } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

export interface TimelineItem {
  id: string | number;
  title: React.ReactNode;
  description?: React.ReactNode;
  timestamp: string;
  icon?: LucideIcon;
  tone?: "default" | "primary" | "success" | "warning";
  href?: string;
}

const TONE_DOT: Record<NonNullable<TimelineItem["tone"]>, string> = {
  default: "bg-slate-400",
  primary: "bg-primary",
  success: "bg-success",
  warning: "bg-warning",
};

/** Vertical timeline - version history, audit log entries, or any
 * chronological event list. Each item is optionally a link (version
 * history entries navigate to that version's estimate page). */
export function Timeline({ items }: { items: TimelineItem[] }) {
  return (
    <ol className="relative flex flex-col gap-6 pl-2">
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        const content = (
          <div className="flex flex-1 items-start justify-between gap-4">
            <div className="flex flex-col gap-0.5">
              <p className="text-sm font-medium text-foreground">{item.title}</p>
              {item.description && <p className="text-sm text-muted-foreground">{item.description}</p>}
            </div>
            <time className="shrink-0 whitespace-nowrap text-xs text-muted-foreground">{item.timestamp}</time>
          </div>
        );
        return (
          <li key={item.id} className="relative flex gap-4">
            <div className="relative flex flex-col items-center">
              <span
                className={cn(
                  "z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-white",
                  TONE_DOT[item.tone ?? "default"],
                )}
              >
                {item.icon ? <item.icon className="h-3 w-3" /> : <span className="h-1.5 w-1.5 rounded-full bg-white" />}
              </span>
              {!isLast && <span className="mt-1 w-px flex-1 bg-border" aria-hidden="true" />}
            </div>
            {item.href ? (
              <Link href={item.href} className="-mx-2 flex-1 rounded-md px-2 py-0.5 transition-colors hover:bg-muted/60">
                {content}
              </Link>
            ) : (
              <div className="flex-1 py-0.5">{content}</div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
