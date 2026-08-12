import { Lightbulb } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import type { Assumption } from "@/lib/types";

export function AssumptionsList({ assumptions }: { assumptions: Assumption[] }) {
  if (assumptions.length === 0) {
    return (
      <EmptyState
        icon={Lightbulb}
        title="No assumptions were made"
        description="Every value was used exactly as requested - nothing was substituted."
      />
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {assumptions.map((a, i) => (
        <li key={`${a.field}-${i}`} className="flex items-start gap-2.5 rounded-md border border-border p-3 text-sm">
          <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <div className="flex flex-col gap-0.5">
            <p className="font-medium text-foreground">{a.field}</p>
            <p className="text-muted-foreground">
              Requested <span className="font-mono text-[13px]">{a.requested_value}</span> &rarr; used{" "}
              <span className="font-mono text-[13px]">{a.used_value}</span>
            </p>
            <p className="text-muted-foreground">{a.reason}</p>
            {a.strategy_applied && <p className="text-xs text-muted-foreground/70">strategy: {a.strategy_applied}</p>}
          </div>
        </li>
      ))}
    </ul>
  );
}
