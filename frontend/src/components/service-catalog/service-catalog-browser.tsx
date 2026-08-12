"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";
import { catalogApi } from "@/lib/api-client";
import type { GCPServiceDefinition } from "@/lib/types";

import { ServiceCard } from "./service-card";

export function ServiceCatalogBrowser({
  getSelectedCount,
  getAddState,
  onAddService,
}: {
  getSelectedCount: (serviceId: string) => number;
  getAddState: (definition: GCPServiceDefinition) => { disabled: boolean; label?: string };
  onAddService: (definition: GCPServiceDefinition) => void;
}) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);

  const servicesQuery = useQuery({ queryKey: ["catalog-services"], queryFn: () => catalogApi.services() });
  const categoriesQuery = useQuery({ queryKey: ["catalog-service-categories"], queryFn: catalogApi.serviceCategories });

  const filtered = useMemo(() => {
    const services = servicesQuery.data ?? [];
    // Strip punctuation/spaces on both sides so "pubsub" still matches
    // "Pub/Sub", "cloud sql" matches "Cloud SQL", etc.
    const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");
    const needle = normalize(search.trim());
    return services.filter((s) => {
      if (category && s.category !== category) return false;
      if (needle && !normalize(s.display_name).includes(needle) && !normalize(s.description).includes(needle)) return false;
      return true;
    });
  }, [servicesQuery.data, search, category]);

  return (
    <div className="flex flex-col gap-4">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search GCP services..."
          className="pl-9"
        />
      </div>

      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setCategory(null)}
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            category === null ? "border-primary bg-primary text-primary-foreground" : "border-border text-muted-foreground hover:bg-muted",
          )}
        >
          All
        </button>
        {(categoriesQuery.data ?? []).map((cat) => (
          <button
            key={cat}
            type="button"
            onClick={() => setCategory((prev) => (prev === cat ? null : cat))}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
              category === cat ? "border-primary bg-primary text-primary-foreground" : "border-border text-muted-foreground hover:bg-muted",
            )}
          >
            {cat}
          </button>
        ))}
      </div>

      {servicesQuery.isLoading ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={Search} title="No services found" description="Try a different search term or category." />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((definition) => {
            const addState = getAddState(definition);
            return (
              <ServiceCard
                key={definition.service_id}
                definition={definition}
                selectedCount={getSelectedCount(definition.service_id)}
                disabled={addState.disabled}
                disabledLabel={addState.label}
                onAdd={() => onAddService(definition)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
