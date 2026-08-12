import { cn } from "@/lib/utils";

const PALETTE = [
  "bg-primary-100 text-primary-800 dark:bg-primary-950 dark:text-primary-300",
  "bg-success-50 text-success-700 dark:bg-success-900/40 dark:text-success-200",
  "bg-warning-50 text-warning-700 dark:bg-warning-900/40 dark:text-warning-200",
  "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
];

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function paletteIndex(name: string): number {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  return hash % PALETTE.length;
}

export function Avatar({
  name,
  size = "md",
  className,
}: {
  name: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizeClasses = { sm: "h-7 w-7 text-xs", md: "h-9 w-9 text-sm", lg: "h-12 w-12 text-base" };
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold",
        sizeClasses[size],
        PALETTE[paletteIndex(name)],
        className,
      )}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}
