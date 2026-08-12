"use client";

import { Check, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { GCPServiceDefinition } from "@/lib/types";

import { serviceIcon } from "./service-icons";

export function ServiceCard({
  definition,
  selectedCount,
  disabled,
  disabledLabel,
  onAdd,
}: {
  definition: GCPServiceDefinition;
  selectedCount: number;
  disabled?: boolean;
  disabledLabel?: string;
  onAdd: () => void;
}) {
  const Icon = serviceIcon(definition.icon);
  const selected = selectedCount > 0;

  return (
    <div
      data-testid={`service-card-${definition.service_id}`}
      className={cn(
        "flex flex-col gap-3 rounded-lg border p-4 transition-colors",
        selected ? "border-primary bg-primary-50 dark:bg-primary-950" : "border-border hover:bg-muted/40",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted">
          {/* `Icon` is a lookup into service-icons.ts's fixed ICONS map, not a
              component defined during render - eslint's static-components
              check can't verify that from a function call, so it flags this
              standard "icon by name" pattern as a false positive. */}
          {/* eslint-disable-next-line react-hooks/static-components */}
          <Icon className="h-4.5 w-4.5 text-foreground" />
        </div>
        {selected && (
          <Badge variant="default" className="shrink-0">
            <Check className="h-3 w-3" />
            {selectedCount > 1 ? `Added ×${selectedCount}` : "Added"}
          </Badge>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium text-foreground">{definition.display_name}</p>
        <p className="text-xs leading-relaxed text-muted-foreground">{definition.description}</p>
      </div>

      <Button
        type="button"
        size="sm"
        variant={selected ? "outline" : "secondary"}
        className="mt-auto self-start"
        disabled={disabled}
        onClick={onAdd}
        title={disabled ? disabledLabel : undefined}
      >
        <Plus className="h-3.5 w-3.5" />
        {disabled ? (disabledLabel ?? "Configured") : selected ? "Add another" : "Add"}
      </Button>
    </div>
  );
}
