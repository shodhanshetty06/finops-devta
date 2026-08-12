import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";

/** Shared label+control+hint wrapper, matching the layout `components/wizard/steps.tsx`
 * uses locally - kept here as a small reusable version for non-wizard forms
 * (e.g. optimization panels) rather than duplicating the markup inline. */
export function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
