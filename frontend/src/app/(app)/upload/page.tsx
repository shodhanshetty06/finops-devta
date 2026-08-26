"use client";

import { AlertTriangle, CheckCircle2, Download, FileSpreadsheet, FileText, Info, Sparkles, Upload as UploadIcon, XCircle } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { AssumptionsList } from "@/components/assumptions-list";
import { EstimateResultView } from "@/components/estimate-result-view";
import { SaveToProjectDialog } from "@/components/save-to-project-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useSetAssistantEstimate } from "@/contexts/assistant-context";
import { useCurrency } from "@/contexts/currency-context";
import { apiErrorMessage, downloadReport, estimateApi, intakeApi, reportsApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { REGIONS, type EstimateResult, type IntakeResponse, type ParseIssue, type RegionCode } from "@/lib/types";

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

/** Every field this page owns, cleared together by resetState() - no piece
 * of a previous upload (or a previous Quick Estimate on another page,
 * which lives in its own separate component state entirely) can ever leak
 * into the next upload. */
function initialState() {
  return {
    selectedFileName: null as string | null,
    response: null as IntakeResponse | null,
    selectedRegion: null as RegionCode | null,
    saveDialogOpen: false,
  };
}

export default function UploadExcelPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isPricing, setIsPricing] = useState(false);
  const [state, setState] = useState(initialState);
  const { selectedFileName, response, selectedRegion, saveDialogOpen } = state;
  useSetAssistantEstimate(response?.estimate ?? null);

  function resetState() {
    setState(initialState());
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    // A fresh calculation context starts the instant a new/replacement file
    // is chosen - the previous file's requirement, issues, estimate, and
    // region selection are all wiped before the new upload is even sent,
    // so nothing from the old file can end up mixed into the new one.
    setState({ ...initialState(), selectedFileName: file.name });
    setIsUploading(true);
    try {
      const result = await intakeApi.uploadExcel(file, false);
      setState((prev) => ({ ...prev, response: result }));
      if (result.requirement) {
        toast.success(
          result.extraction_source === "ai"
            ? "Workbook understood via AI-assisted extraction - review the results below"
            : "Questionnaire parsed",
        );
      } else {
        toast.error("Could not confidently read this workbook");
      }
    } catch (err) {
      toast.error("Could not process the workbook", { description: apiErrorMessage(err) });
      setState((prev) => ({ ...prev, response: null }));
    } finally {
      setIsUploading(false);
    }
  }

  async function handleCalculatePrice(force: boolean) {
    if (!response?.requirement) return;
    setIsPricing(true);
    try {
      // Region override is opt-in: if the user picked one above it wins,
      // otherwise the region already parsed from the workbook is used as-is.
      const requirement = selectedRegion ? { ...response.requirement, region: selectedRegion } : response.requirement;
      const estimate = await estimateApi.create(requirement, { force });
      setState((prev) => ({ ...prev, response: prev.response ? { ...prev.response, requirement, estimate } : prev.response }));
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
        <p className="text-sm text-muted-foreground">
          Upload any customer requirements workbook - our own template or an arbitrary layout. Every field is parsed
          and flagged transparently, and nothing is priced until you choose a region and calculate.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>1. Get the template (optional)</CardTitle>
          <CardDescription>
            Works with any customer workbook layout - but the standard template parses instantly with no AI step.
          </CardDescription>
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
                <Button type="button" variant="ghost" size="sm" onClick={resetState} disabled={isUploading}>
                  <XCircle className="h-4 w-4" />
                  Remove / Reset
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
              <span className="text-xs text-muted-foreground">or drag and drop - any layout is fine</span>
              <input ref={fileInputRef} type="file" accept=".xlsx" onChange={handleFileChange} disabled={isUploading} className="hidden" />
            </label>
          )}
        </CardContent>
      </Card>

      {response && (
        <>
          {response.extraction_source === "ai" && (
            <div className="flex items-center gap-2 rounded-md border border-primary-200 bg-primary-50 px-3 py-2 text-sm text-primary-700 dark:border-primary-900 dark:bg-primary-950 dark:text-primary-300">
              <Sparkles className="h-4 w-4 shrink-0" />
              This workbook didn&apos;t match our standard layout, so it was read with AI-assisted extraction. Every
              value below still comes only from your file - review the assumptions and mapping warnings before pricing.
            </div>
          )}

          {response.requirement === null && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-error-700 dark:text-error-300">
                  <XCircle className="h-4 w-4" />
                  We could not confidently identify the required cloud resources
                </CardTitle>
                <CardDescription>
                  Please review the details below, then either fix the workbook and re-upload, or download the
                  standard template and fill it in directly.
                </CardDescription>
              </CardHeader>
            </Card>
          )}

          {response.issues.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {response.requirement ? "Mapping warnings" : "Details"}
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
                  Assumptions
                  <Badge variant="secondary">{response.notes.length}</Badge>
                </CardTitle>
                <CardDescription>Anything inferred or converted from your workbook, explained plainly.</CardDescription>
              </CardHeader>
              <CardContent>
                <AssumptionsList assumptions={response.notes} />
              </CardContent>
            </Card>
          )}

          {response.requirement && !response.estimate && (
            <Card>
              <CardHeader>
                <CardTitle>3. Region &amp; pricing (optional)</CardTitle>
                <CardDescription>
                  By default pricing uses the region from your workbook. Only pick one below to override it.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="flex flex-col gap-1.5 sm:max-w-xs">
                  <Label htmlFor="region">Region override</Label>
                  <Select
                    id="region"
                    value={selectedRegion ?? ""}
                    onChange={(e) =>
                      setState((prev) => ({ ...prev, selectedRegion: (e.target.value || null) as RegionCode | null }))
                    }
                  >
                    <option value="">Use region from workbook</option>
                    {REGIONS.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  {(() => {
                    const hasBlockers = response.issues.some((issue) => issue.severity === "blocker");
                    return (
                      <Button size="sm" onClick={() => handleCalculatePrice(hasBlockers)} disabled={isPricing}>
                        {isPricing ? <Spinner /> : null}
                        {hasBlockers ? "Force calculate price anyway" : "Calculate Price"}
                      </Button>
                    );
                  })()}
                </div>
                <details className="text-xs text-muted-foreground">
                  <summary className="cursor-pointer select-none">View extracted requirement (JSON)</summary>
                  <pre className="mt-2 overflow-x-auto rounded-md bg-muted p-4">{JSON.stringify(response.requirement, null, 2)}</pre>
                </details>
              </CardContent>
            </Card>
          )}

          {response.estimate && (
            <>
              <div className="flex items-center justify-between gap-3">
                <p className="flex items-center gap-2 text-sm text-success-700 dark:text-success-400">
                  <CheckCircle2 className="h-4 w-4" />
                  Priced successfully in {response.requirement?.region}
                </p>
                <div className="flex items-center gap-2">
                  <ExportEstimateButtons estimate={response.estimate} />
                  <Button size="sm" onClick={() => setState((prev) => ({ ...prev, saveDialogOpen: true }))}>
                    Save Estimate
                  </Button>
                  <Button variant="outline" size="sm" onClick={resetState}>
                    Reset
                  </Button>
                </div>
              </div>
              <EstimateResultView result={response.estimate} />
              {response.requirement && (
                <SaveToProjectDialog
                  open={saveDialogOpen}
                  onOpenChange={(open) => setState((prev) => ({ ...prev, saveDialogOpen: open }))}
                  requirement={response.requirement}
                  commitmentTermYears={0}
                />
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
