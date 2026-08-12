"use client";

import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

export function Stepper({
  steps,
  currentIndex,
  onStepClick,
}: {
  steps: readonly string[];
  currentIndex: number;
  onStepClick?: (index: number) => void;
}) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-3">
      {steps.map((step, i) => {
        const isComplete = i < currentIndex;
        const isCurrent = i === currentIndex;
        return (
          <li key={step} className="flex items-center gap-2">
            <button
              type="button"
              disabled={!onStepClick}
              onClick={() => onStepClick?.(i)}
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-full border text-xs font-medium transition-colors",
                isComplete && "border-primary bg-primary text-primary-foreground",
                isCurrent && !isComplete && "border-primary text-primary",
                !isComplete && !isCurrent && "border-border-strong text-muted-foreground",
                onStepClick && "cursor-pointer",
              )}
            >
              {isComplete ? <Check className="h-3.5 w-3.5" /> : i + 1}
            </button>
            <span className={cn("hidden text-xs font-medium sm:inline", isCurrent ? "text-foreground" : "text-muted-foreground")}>
              {step}
            </span>
            {i < steps.length - 1 && <span className="mx-1 h-px w-4 bg-border-strong sm:w-6" />}
          </li>
        );
      })}
    </ol>
  );
}
