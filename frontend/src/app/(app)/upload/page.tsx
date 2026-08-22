"use client";

import { AlertTriangle, CheckCircle2, Download, FileSpreadsheet, FileText, Info, Upload as UploadIcon, XCircle } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { AssumptionsList } from "@/components/assumptions-list";
import { EstimateResultView } from "@/components/estimate-result-view";
import { SaveToProjectDialog } from "@/components/save-to-project-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Spinner } from "@/components/ui/spinner";
import { useSetAssistantEstimate } from "@/contexts/assistant-context";
import { useCurrency } from "@/contexts/currency-context";
import { apiErrorMessage, downloadReport, estimateApi, intakeApi, reportsApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { EstimateResult, IntakeResponse, ParseIssue } from "@/lib/types";

function IssueIcon({ severity }: { severity: ParseIssue["severity"] }) {
  if (severity === "blocker") return <XCircle className="h-4 w-4 shrink-0" />;
  if (severity === "warning") return <AlertTriangle className="h-4 w-4 shrink-0" />;
  return <Info className="h-4 w-4 shrink-0" />;
}

function issueClasses(severity: ParseIssue["severity"]): string {
  switch (severity) {
    case "blocker":
      return "text-error-700 bg-error-50 border-error-200 dark:text-error-300 dark:bg-error-900/20 dark:border-error-900";
    case "warning":
      return "text-warning-700 bg-warning-50 border-warning-200 dark:text-warning-300 dark:bg-warning-900/20 dark:border-warning-900";
    default:
      return "text-primary-700 bg-primary-50 border-primary-200 dark:text-primary-300 dark:bg-primary-950 dark:border-primary-900";
  }
}

function ExportEstimateButtons({ estimate }: { estimate: EstimateResult }) {
  const [downloading, setDownloading] = useState<"excel" | "pdf" | null>(null);
  const { displayCurrency } = useCurrency();

  async function handleExport(kind: "excel" | "pdf") {
    setDownloading(kind);
    try {
      const url = kind === "excel" ? reportsApi.exportExcelUrl() : reportsApi.exportPdfUrl();
      const ext = kind === "excel" ? "xlsx" : "pdf";
      const filename = `${estimate.project_name.replace(/[^a-zA-Z0-9]+/g, "_")}_estimate.${ext}`;
      // Renders the report in whatever currency is currently selected on
      // screen (see useCurrency()) - the backend converts every figure via
      // CurrencyConverter.convert_estimate before rendering, or falls back
      // to the estimate's native currency if a rate isn't available.
      await downloadReport(url, filename, { estimate, target_currency: displayCurrency });
    } catch (err) {
      toast.error(`Could not export ${kind.toUpperCase()}`, { description: apiErrorMessage(err) });
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={() => handleExport("excel")} disabled={downloading !== null}>
        {downloading === "excel" ? <Spinner /> : <FileSpreadsheet className="h-4 w-4" />}
        Export Excel
      </Button>
      <Button variant="outline" size="sm" onClick={() => handleExport("pdf")} disabled={downloading !== null}>
        {downloading === "pdf" ? <Spinner /> : <FileText className="h-4 w-4" />}
        Export PDF
      </Button>
    </div>
  );
}

export default function UploadExcelPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [autoEstimate, setAutoEstimate] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isPricing, setIsPricing] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [response, setResponse] = useState<IntakeResponse | null>(null);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  useSetAssistantEstimate(response?.estimate ?? null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFileName(file.name);
    setResponse(null);
    setIsUploading(true);
    try {
      const result = await intakeApi.uploadExcel(file, autoEstimate);
      setResponse(result);
      toast.success(result.estimate ? "Questionnaire parsed and priced" : "Questionnaire parsed");
    } catch (err) {
      toast.error("Could not process the workbook", { description: apiErrorMessage(err) });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function handleRemoveFile() {
    setSelectedFileName(null);
    setResponse(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handlePriceNow(force: boolean) {
    if (!response?.requirement) return;
    setIsPricing(true);
    try {
      const estimate = await estimateApi.create(response.requirement, { force });
      setResponse((prev) => (prev ? { ...prev, estimate } : prev));
      toast.success("Priced successfully");
    } catch (err) {
      toast.error("Could not price this requirement", { description: apiErrorMessage(err) });
    } finally {
      setIsPricing(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Upload Excel</h1>
        <p className="text-sm text-muted-foreground">Import a filled questionnaire workbook - every field is parsed and flagged transparently.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>1. Get the template</CardTitle>
          <CardDescription>Download the blank questionnaire, fill it in offline, then come back and upload it below.</CardDescription>
        </CardHeader>
        <CardContent>
          <a href={intakeApi.templateUrl()} download>
            <Button type="button" variant="outline">
              <Download className="h-4 w-4" />
              Download template (.xlsx)
            </Button>
          </a>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Upload it</CardTitle>
          <CardDescription>Parses every field and shows exactly what couldn&apos;t be confidently read.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <label className="flex items-center gap-2 text-sm text-foreground">
            <Checkbox checked={autoEstimate} onChange={(e) => setAutoEstimate(e.target.checked)} />
            Automatically price the result once parsed
          </label>

          {selectedFileName ? (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-border-strong px-4 py-3">
              <div className="flex min-w-0 items-center gap-2 text-sm text-foreground">
                {isUploading ? <Spinner className="h-4 w-4 shrink-0" /> : <FileSpreadsheet className="h-4 w-4 shrink-0 text-muted-foreground" />}
                <span className="truncate font-medium">{selectedFileName}</span>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <label className={cn("cursor-pointer", isUploading && "pointer-events-none opacity-60")}>
                  <span className="px-2 text-sm font-medium text-primary-600 hover:underline">Replace</span>
                  <input ref={fileInputRef} type="file" accept=".xlsx" onChange={handleFileChange} disabled={isUploading} className="hidden" />
                </label>
                <Button type="button" variant="ghost" size="sm" onClick={handleRemoveFile} disabled={isUploading}>
                  <XCircle className="h-4 w-4" />
                  Remove
                </Button>
              </div>
            </div>
          ) : (
            <label
              className={cn(
                "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border-strong px-6 py-10 text-center transition-colors hover:border-primary-300 hover:bg-muted/40",
                isUploading && "pointer-events-none opacity-60",
              )}
            >
              {isUploading ? <Spinner className="h-6 w-6 text-muted-foreground" /> : <UploadIcon className="h-6 w-6 text-muted-foreground" />}
              <span className="text-sm font-medium text-foreground">{isUploading ? "Processing..." : "Click to choose a .xlsx file"}</span>
              <span className="text-xs text-muted-foreground">or drag and drop</span>
              <input ref={fileInputRef} type="file" accept=".xlsx" onChange={handleFileChange} disabled={isUploading} className="hidden" />
            </label>
          )}
        </CardContent>
      </Card>

      {response && (
        <>
          {response.issues.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  Parse issues
                  <Badge variant="secondary">{response.issues.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col gap-2">
                  {response.issues.map((issue, i) => (
                    <li key={i} className={cn("flex items-start gap-2 rounded-md border px-3 py-2 text-sm", issueClasses(issue.severity))}>
                      <IssueIcon severity={issue.severity} />
                      <div className="flex flex-col gap-0.5">
                        <span className="font-medium">{issue.field}</span>
                        <span>{issue.message}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {response.notes.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  Inferred assumptions
                  <Badge variant="secondary">{response.notes.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <AssumptionsList assumptions={response.notes} />
              </CardContent>
            </Card>
          )}

          {response.estimate ? (
            <>
              <div className="flex items-center justify-between gap-3">
                <p className="flex items-center gap-2 text-sm text-success-700 dark:text-success-400">
                  <CheckCircle2 className="h-4 w-4" />
                  Priced successfully
                </p>
                <div className="flex items-center gap-2">
                  <ExportEstimateButtons estimate={response.estimate} />
                  <Button size="sm" onClick={() => setSaveDialogOpen(true)}>
                    Save to a project
                  </Button>
                </div>
              </div>
              <EstimateResultView result={response.estimate} />
              {response.requirement && (
                <SaveToProjectDialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen} requirement={response.requirement} commitmentTermYears={0} />
              )}
            </>
          ) : (
            response.requirement && (() => {
              const hasBlockers = response.issues.some((issue) => issue.severity === "blocker");
              return (
                <Card>
                  <CardHeader>
                    <CardTitle>Parsed requirement</CardTitle>
                    <CardDescription>
                      {hasBlockers
                        ? "Pricing was blocked by the issue(s) marked above. Resolve them and re-upload, or force a price anyway."
                        : "Automatic pricing was off for this upload. Review the parsed data below, then price it whenever you're ready."}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-4">
                    <div>
                      <Button size="sm" onClick={() => handlePriceNow(hasBlockers)} disabled={isPricing}>
                        {isPricing ? <Spinner /> : null}
                        {hasBlockers ? "Force price anyway" : "Price this now"}
                      </Button>
                    </div>
                    <pre className="overflow-x-auto rounded-md bg-muted p-4 text-xs text-foreground">
                      {JSON.stringify(response.requirement, null, 2)}
                    </pre>
                  </CardContent>
                </Card>
              );
            })()
          )}
        </>
      )}
    </div>
  );
}
