import { ArchitectureDiagram } from "@/components/architecture-diagram";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ArchitectureRecommendation } from "@/lib/types";

export function ArchitecturePanel({ architecture }: { architecture: ArchitectureRecommendation }) {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{architecture.summary}</p>
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <ArchitectureDiagram components={architecture.components} />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {architecture.components.map((c) => (
          <Card key={`${c.layer}-${c.service}`}>
            <CardHeader className="pb-1">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{c.layer}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="font-medium text-foreground">{c.service}</p>
              <p className="mt-1 text-sm text-muted-foreground">{c.rationale}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
