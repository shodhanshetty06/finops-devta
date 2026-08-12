"use client";

import { ArrowDown, ArrowUp, Scale } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AssumptionsList } from "@/components/assumptions-list";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
  AvailabilityStep,
  BasicsStep,
  DatabaseStep,
  KubernetesStep,
  NetworkStep,
  SizingStep,
  StorageStep,
} from "@/components/wizard/steps";
import { useWizardState } from "@/components/wizard/use-wizard-state";
import { apiErrorMessage, estimateApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { Assumption, NormalizationStrategy } from "@/lib/types";

const STRATEGIES: {
  value: NormalizationStrategy;
  label: string;
  icon: typeof ArrowDown;
  summary: string;
  detail: string;
}[] = [
  {
    value: "conservative",
    label: "Conservative",
    icon: ArrowDown,
    summary: "Nearest lower supported value",
    detail: "Favors cost control - rounds an unsupported request down to the closest smaller supported option (e.g. 6 vCPU requested, 4 vCPU offered → picks 4).",
  },
  {
    value: "balanced",
    label: "Balanced",
    icon: Scale,
    summary: "Mathematically closest value (default)",
    detail: "Picks whichever supported value is numerically nearest to what was requested, in either direction - ties resolve upward.",
  },
  {
    value: "performance",
    label: "Performance",
    icon: ArrowUp,
    summary: "Nearest higher supported value",
    detail: "Favors headroom and SLA margin - rounds an unsupported request up to the closest larger supported option, even if that costs more.",
  },
];

const SECTIONS = [
  { name: "Basics", component: BasicsStep },
  { name: "Sizing", component: SizingStep },
  { name: "Storage", component: StorageStep },
  { name: "Database", component: DatabaseStep },
  { name: "Network", component: NetworkStep },
  { name: "Kubernetes", component: KubernetesStep },
  { name: "Availability", component: AvailabilityStep },
] as const;

export default function NormalizationPage() {
  const state = useWizardState();
  const [assumptions, setAssumptions] = useState<Assumption[] | null>(null);
  const [strategyUsed, setStrategyUsed] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  async function handleRun() {
    setIsRunning(true);
    try {
      const result = await estimateApi.create(state.requirement, { force: true });
      setAssumptions(result.assumptions);
      setStrategyUsed(result.strategy_used);
      toast.success(result.assumptions.length > 0 ? `${result.assumptions.length} assumption(s) made` : "No assumptions needed - everything matched exactly");
    } catch (err) {
      toast.error("Could not run normalization", { description: apiErrorMessage(err) });
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Normalization</h1>
        <p className="text-sm text-muted-foreground">
          How ambiguous or unsupported input gets resolved to a real, purchasable configuration - and exactly what changed.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {STRATEGIES.map((s) => (
          <Card key={s.value} className={cn(state.requirement.normalization_strategy === s.value && "border-primary-300 ring-1 ring-primary-200 dark:border-primary-800 dark:ring-primary-900")}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <s.icon className="h-4 w-4 text-primary" />
                {s.label}
              </CardTitle>
              <CardDescription>{s.summary}</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{s.detail}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Try it</CardTitle>
          <CardDescription>
            Fill in a configuration - pick a strategy in Basics - and see exactly which fields get substituted and why. This
            runs the real pricing pipeline (force-applied) purely to observe its assumptions.
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          {SECTIONS.map(({ name, component: StepComponent }) => (
            <Card key={name}>
              <CardHeader>
                <CardTitle className="text-sm">{name}</CardTitle>
              </CardHeader>
              <CardContent>
                <StepComponent state={state} />
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="flex flex-col gap-4">
          <Card className="sticky top-20">
            <CardHeader>
              <CardTitle className="text-sm">Assumptions made</CardTitle>
              {strategyUsed && <CardDescription>Strategy applied: {strategyUsed}</CardDescription>}
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Button onClick={handleRun} disabled={isRunning || !state.requirement.project_name}>
                {isRunning && <Spinner />}
                Run normalization
              </Button>
              {!state.requirement.project_name && <p className="text-xs text-muted-foreground">Set a project name in Basics first.</p>}
              {assumptions && <AssumptionsList assumptions={assumptions} />}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
