import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { ValidationReport, ValidationResult } from "@/lib/types";

function SeverityBadge({ severity }: { severity: ValidationResult["severity"] }) {
  if (severity === "blocker") return <Badge variant="destructive"><XCircle />Blocker</Badge>;
  if (severity === "warning") return <Badge variant="warning"><AlertTriangle />Warning</Badge>;
  return <Badge variant="default"><Info />Info</Badge>;
}

/** Full tabular validation report - every field/rule/reason/recommendation
 * column visible at once. Used on the Validation page's live-validator tool
 * and the estimate result page. See ValidationPanel for the compact,
 * card-embedded variant used inside the wizard. */
export function ValidationTable({ report }: { report: ValidationReport | null }) {
  if (!report || report.results.length === 0) {
    return (
      <EmptyState
        icon={CheckCircle2}
        title="No issues found"
        description="This configuration is fully supported as requested - nothing was substituted or flagged."
      />
    );
  }

  const ordered = [...report.results].sort((a, b) => {
    const order = { blocker: 0, warning: 1, info: 2 };
    return order[a.severity] - order[b.severity];
  });

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Severity</TableHead>
          <TableHead>Field</TableHead>
          <TableHead>Requested</TableHead>
          <TableHead>Supported</TableHead>
          <TableHead>Reason</TableHead>
          <TableHead>Recommendation</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {ordered.map((r, i) => (
          <TableRow key={`${r.field}-${r.rule}-${i}`}>
            <TableCell>
              <SeverityBadge severity={r.severity} />
            </TableCell>
            <TableCell className="font-medium text-foreground">{r.field}</TableCell>
            <TableCell className="text-muted-foreground">{r.requested_value}</TableCell>
            <TableCell className="text-muted-foreground">{r.supported_value ?? "—"}</TableCell>
            <TableCell className="whitespace-normal text-muted-foreground">{r.reason}</TableCell>
            <TableCell className="whitespace-normal text-muted-foreground">{r.recommendation || "—"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
