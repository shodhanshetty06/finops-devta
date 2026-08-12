"use client";

import { useCallback, useMemo, useState } from "react";

import { getDefaultNormalizationStrategy } from "@/lib/preferences";
import type {
  AvailabilityRequirement,
  BusinessContext,
  ComputeRequirement,
  CustomerRequirement,
  DatabaseRequirement,
  KubernetesRequirement,
  NetworkRequirement,
  StorageRequirement,
} from "@/lib/types";

export type SizingMode = "explicit" | "business";

const DEFAULT_COMPUTE: ComputeRequirement = {
  machine_family: "e2",
  vcpu: 4,
  ram_gb: 16,
  instance_count: 1,
  gpu_type: "none",
  gpu_count: 0,
  provisioning_model: "on_demand",
  operating_system: "linux",
  hours_per_day: null,
  days_per_month: null,
};

const DEFAULT_STORAGE: StorageRequirement = {
  disk_type: "pd-balanced",
  size_gb: 100,
  snapshot_enabled: false,
  snapshot_retention_days: 7,
  snapshot_storage_gb: 0,
  provisioned_iops: 0,
  provisioned_throughput_mbps: 0,
  additional_disks: [],
  local_ssd_count: 0,
};

const DEFAULT_DATABASE: DatabaseRequirement = {
  required: true,
  engine: "postgres",
  machine_tier: "custom",
  size_gb: 50,
  storage_type: "ssd",
  vcpu: 2,
  ram_gb: 8,
  high_availability: false,
  backup_storage_gb: 0,
  binary_log_storage_gb: 0,
  commitment: "none",
};

const DEFAULT_NETWORK: NetworkRequirement = {
  load_balancer_required: false,
  external_ip_count: 1,
  estimated_egress_gb_per_month: 100,
  estimated_ingress_gb_per_month: 0,
  cdn_enabled: false,
  vpn_required: false,
};

const DEFAULT_KUBERNETES: KubernetesRequirement = {
  required: true,
  node_count: 3,
  autopilot: false,
};

const DEFAULT_AVAILABILITY: AvailabilityRequirement = {
  high_availability: false,
  target_uptime_percent: 99.9,
  backup_frequency: "daily",
  disaster_recovery_required: false,
};

const DEFAULT_BUSINESS: BusinessContext = {
  total_users: 500,
  peak_concurrent_users: 100,
  notes: null,
};

export function emptyRequirement(): CustomerRequirement {
  return {
    project_name: "",
    region: "us-central1",
    normalization_strategy: getDefaultNormalizationStrategy(),
    compute: null,
    storage: null,
    database: null,
    network: null,
    kubernetes: null,
    availability: null,
    business: null,
    selected_services: [],
    existing_infrastructure_notes: null,
  };
}

export const WIZARD_STEPS = [
  "Basics",
  "Sizing",
  "Storage",
  "Database",
  "Network",
  "Kubernetes",
  "Availability",
  "Review",
] as const;
export type WizardStepName = (typeof WIZARD_STEPS)[number];

export function useWizardState(initial?: CustomerRequirement) {
  const [requirement, setRequirement] = useState<CustomerRequirement>(initial ?? emptyRequirement());
  const [sizingMode, setSizingMode] = useState<SizingMode>(initial?.compute ? "explicit" : "business");
  const [stepIndex, setStepIndex] = useState(0);

  const update = useCallback(<K extends keyof CustomerRequirement>(key: K, value: CustomerRequirement[K]) => {
    setRequirement((prev) => ({ ...prev, [key]: value }));
  }, []);

  const toggleSection = useCallback(
    <K extends "storage" | "database" | "network" | "kubernetes" | "availability">(
      key: K,
      enabled: boolean,
      defaults: CustomerRequirement[K],
    ) => {
      setRequirement((prev) => ({ ...prev, [key]: enabled ? defaults : null }));
    },
    [],
  );

  const setSizing = useCallback((mode: SizingMode) => {
    setSizingMode(mode);
    setRequirement((prev) => ({
      ...prev,
      compute: mode === "explicit" ? (prev.compute ?? DEFAULT_COMPUTE) : null,
      business: mode === "business" ? (prev.business ?? DEFAULT_BUSINESS) : null,
    }));
  }, []);

  const goNext = useCallback(() => setStepIndex((i) => Math.min(i + 1, WIZARD_STEPS.length - 1)), []);
  const goBack = useCallback(() => setStepIndex((i) => Math.max(i - 1, 0)), []);
  const goToStep = useCallback((i: number) => setStepIndex(Math.min(Math.max(i, 0), WIZARD_STEPS.length - 1)), []);

  const currentStepName = useMemo(() => WIZARD_STEPS[stepIndex], [stepIndex]);

  return {
    requirement,
    setRequirement,
    update,
    toggleSection,
    sizingMode,
    setSizing,
    stepIndex,
    currentStepName,
    goNext,
    goBack,
    goToStep,
    defaults: {
      compute: DEFAULT_COMPUTE,
      storage: DEFAULT_STORAGE,
      database: DEFAULT_DATABASE,
      network: DEFAULT_NETWORK,
      kubernetes: DEFAULT_KUBERNETES,
      availability: DEFAULT_AVAILABILITY,
      business: DEFAULT_BUSINESS,
    },
  };
}

export type WizardState = ReturnType<typeof useWizardState>;
