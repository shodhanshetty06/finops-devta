"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Copy, Layers, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { GCPServiceDefinition, ValidationReport } from "@/lib/types";

import type { SelectedServiceEntry } from "@/components/wizard/use-service-selection";
import { DynamicServiceConfigForm } from "./dynamic-service-config-form";
import { serviceIcon } from "./service-icons";

export function SelectedServicesPanel({
  entries,
  definitionsById,
  validation,
  canDuplicate,
  onUpdateConfig,
  onUpdateQuantity,
  onRemove,
  onDuplicate,
}: {
  entries: SelectedServiceEntry[];
  definitionsById: Map<string, GCPServiceDefinition>;
  validation: ValidationReport | null;
  canDuplicate: (definition: GCPServiceDefinition) => boolean;
  onUpdateConfig: (key: string, config: Record<string, unknown>) => void;
  onUpdateQuantity: (key: string, quantity: number) => void;
  onRemove: (key: string) => void;
  onDuplicate: (key: string) => void;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggle(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  if (entries.length === 0) {
    return (
      <EmptyState
        icon={Layers}
        title="No services selected yet"
        description="Search the catalog above and add the GCP services this estimate needs."
      />
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium text-foreground">Selected Services ({entries.length})</p>
      <div className="flex flex-col gap-2">
        {entries.map((entry) => {
          const definition = definitionsById.get(entry.service_id);
          const isOpen = expanded.has(entry.key);
          const issues = (validation?.results ?? []).filter(
            (r) => r.field === `selected_services.${entry.service_id}` && !r.is_valid,
          );
          const Icon = definition ? serviceIcon(definition.icon) : Layers;

          return (
            <div key={entry.key} className="rounded-md border border-border">
              <div className="flex items-center gap-2 p-3">
                <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                <button
                  type="button"
                  onClick={() => toggle(entry.key)}
                  className="flex flex-1 items-center gap-2 text-left text-sm font-medium text-foreground"
                >
                  {definition?.display_name ?? entry.service_id}
                  {issues.length > 0 && <Badge variant="warning">{issues.length} issue{issues.length > 1 ? "s" : ""}</Badge>}
                </button>
                <label className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                  Qty
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={entry.quantity}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => onUpdateQuantity(entry.key, Number(e.target.value))}
                    className="w-16 rounded-md border border-border bg-background px-2 py-1 text-sm text-foreground"
                    aria-label={`Quantity for ${definition?.display_name ?? entry.service_id}`}
                  />
                </label>
                {definition && canDuplicate(definition) && (
                  <Button type="button" variant="ghost" size="icon-sm" title="Duplicate" onClick={() => onDuplicate(entry.key)}>
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                )}
                <Button type="button" variant="ghost" size="icon-sm" title="Remove" onClick={() => onRemove(entry.key)}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
                <Button type="button" variant="ghost" size="icon-sm" title={isOpen ? "Collapse" : "Edit"} onClick={() => toggle(entry.key)}>
                  {isOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </Button>
              </div>
              {isOpen && definition && (
                <div className="border-t border-border p-3">
                  <DynamicServiceConfigForm
                    definition={definition}
                    config={entry.config}
                    onChange={(config) => onUpdateConfig(entry.key, config)}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
