"use client";

import { useTheme } from "next-themes";
import { useEffect, useId, useRef, useState } from "react";

import type { ArchitectureComponent } from "@/lib/types";

function sanitizeId(label: string, index: number): string {
  return `n${index}_${label.replace(/[^a-zA-Z0-9]/g, "")}`;
}

function buildDiagramSource(components: ArchitectureComponent[]): string {
  const lines = ["graph TD"];
  components.forEach((c, i) => {
    const id = sanitizeId(c.layer, i);
    const label = `${c.layer}<br/><b>${c.service}</b>`.replace(/"/g, "'");
    lines.push(`  ${id}["${label}"]`);
    if (i > 0) {
      lines.push(`  ${sanitizeId(components[i - 1].layer, i - 1)} --> ${id}`);
    }
  });
  return lines.join("\n");
}

/** Renders the architecture recommendation as a top-to-bottom flowchart via
 * Mermaid. The backend returns an ordered list of components without
 * explicit edges, so this connects each component to the next in list
 * order - a reasonable approximation of a layered architecture diagram
 * (Frontend -> Backend -> Database -> ...) without the backend needing to
 * model graph topology it doesn't otherwise need. */
export function ArchitectureDiagram({ components }: { components: ArchitectureComponent[] }) {
  const containerId = useId().replace(/:/g, "");
  const containerRef = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (components.length === 0) return;
    let cancelled = false;

    (async () => {
      const mermaid = (await import("mermaid")).default;
      mermaid.initialize({
        startOnLoad: false,
        theme: resolvedTheme === "dark" ? "dark" : "default",
        securityLevel: "strict",
      });
      try {
        const { svg: rendered } = await mermaid.render(`arch-${containerId}`, buildDiagramSource(components));
        if (!cancelled) setSvg(rendered);
      } catch {
        if (!cancelled) setError("Could not render the architecture diagram.");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [components, containerId, resolvedTheme]);

  if (components.length === 0) return <p className="text-sm text-muted-foreground">No architecture components.</p>;
  if (error) return <p className="text-sm text-destructive">{error}</p>;

  return <div ref={containerRef} className="overflow-x-auto" dangerouslySetInnerHTML={svg ? { __html: svg } : undefined} />;
}
