"use client";

import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ValidationTable } from "@/components/finops/validation-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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
import { VALIDATION_RULES_REFERENCE } from "@/lib/validation-rules-reference";
import type { ValidationReport } from "@/lib/types";

const SECTIONS = [
  { name: "Basics", component: BasicsStep },
  { name: "Sizing", component: SizingStep },
  { name: "Storage", component: StorageStep },
  { name: "Database", component: DatabaseStep },
  { name: "Network", component: NetworkStep },
  { name: "Kubernetes", component: KubernetesStep },
  { name: "Availability", component: AvailabilityStep },
] as const;

export default function ValidationPage() {
  const state = useWizardState();
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  async function handleValidate() {
    setIsChecking(true);
    try {
      setReport(await estimateApi.validate(state.requirement));
    } catch (err) {
      toast.error("Could not run validation", { description: apiErrorMessage(err) });
    } finally {
      setIsChecking(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Validation</h1>
        <p className="text-sm text-muted-foreground">
          The rule engine every estimate runs through, plus a tool to check a configuration without pricing it.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Rule reference</CardTitle>
          <CardDescription>All 13 rules the validation engine enforces (backend/app/validation/rules.py)</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Category</TableHead>
                <TableHead>Rule</TableHead>
                <TableHead>Fields inspected</TableHead>
                <TableHead>What it checks</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {VALIDATION_RULES_REFERENCE.map((r) => (
                <TableRow key={r.rule}>
                  <TableCell>
                    <Badge variant="secondary">{r.category}</Badge>
                  </TableCell>
                  <TableCell className="font-mono text-[13px] text-foreground">{r.rule}</TableCell>
                  <TableCell className="text-muted-foreground">{r.fields.join(", ")}</TableCell>
                  <TableCell className="whitespace-normal text-muted-foreground">{r.description}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-1 flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
          <ShieldCheck className="h-4.5 w-4.5 text-muted-foreground" />
          Live validator
        </h2>
        <p className="mb-4 text-sm text-muted-foreground">Fill in a configuration and check it against every rule above, without generating a priced estimate.</p>

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
                <CardTitle className="text-sm">Results</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <Button onClick={handleValidate} disabled={isChecking || !state.requirement.project_name}>
                  {isChecking && <Spinner />}
                  Run validation
                </Button>
                {!state.requirement.project_name && <p className="text-xs text-muted-foreground">Set a project name in Basics first.</p>}
              </CardContent>
            </Card>
          </div>
        </div>

        {report && (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle>Results ({report.results.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <ValidationTable report={report} />
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
