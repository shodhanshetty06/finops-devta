// Human-friendly copy for the Compute Engine family picker (Sizing step).
// Purely presentational - the backend catalog (MachineFamilyCapability) is
// still the only source of truth for what's actually valid/available; this
// just labels the choices so a non-technical customer can scan them.
import type { MachineFamily } from "@/lib/types";

export const FAMILY_CATEGORIES = [
  "General purpose",
  "Compute optimized",
  "Scale-out (cost-optimized)",
  "GPU-accelerated",
] as const;
export type FamilyCategory = (typeof FAMILY_CATEGORIES)[number];

export const FAMILY_INFO: Record<MachineFamily, { category: FamilyCategory; short: string; description: string }> = {
  e2: { category: "General purpose", short: "Cost-optimized", description: "Lowest cost per vCPU - dev/test, web apps, low-traffic services." },
  n1: { category: "General purpose", short: "Legacy general purpose", description: "First-generation general purpose. Prefer N2/N4 for new workloads." },
  n2: { category: "General purpose", short: "Balanced", description: "Balanced price/performance - the default choice for most workloads." },
  n2d: { category: "General purpose", short: "Balanced, AMD", description: "Same as N2 on AMD EPYC - usually a little cheaper." },
  n4: { category: "General purpose", short: "Latest generation", description: "Newest generation general purpose - best price/performance." },
  n4d: { category: "General purpose", short: "Latest generation, AMD", description: "AMD variant of N4, same shape and pricing model." },
  n4a: { category: "General purpose", short: "Arm-based", description: "Arm-based (Axion) - lowest cost per vCPU, limited region availability." },
  c2: { category: "Compute optimized", short: "High per-core performance", description: "High, consistent per-core performance. Fixed sizes only." },
  c3: { category: "Compute optimized", short: "Current generation", description: "Current-generation compute-optimized for CPU-bound workloads." },
  c3d: { category: "Compute optimized", short: "Current generation, AMD", description: "AMD variant of C3." },
  c4: { category: "Compute optimized", short: "Newest generation", description: "Newest-generation compute-optimized." },
  c4d: { category: "Compute optimized", short: "Newest generation, AMD", description: "AMD variant of C4." },
  c4a: { category: "Compute optimized", short: "Arm-based", description: "Arm-based (Axion) compute-optimized, limited region availability." },
  t2d: { category: "Scale-out (cost-optimized)", short: "Scale-out, AMD", description: "AMD Tau - cost-optimized for scale-out workloads. Fixed sizes only." },
  t2a: { category: "Scale-out (cost-optimized)", short: "Scale-out, Arm-based", description: "Arm Tau - cost-optimized scale-out, limited region availability." },
  a2: { category: "GPU-accelerated", short: "GPU-accelerated (A100)", description: "Paired with NVIDIA A100 GPUs, for ML training/inference." },
};

export function familyLabel(family: string): string {
  return family.toUpperCase();
}
