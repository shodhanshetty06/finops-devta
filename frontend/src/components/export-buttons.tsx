"use client";

import { FileSpreadsheet, FileText } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useCurrency } from "@/contexts/currency-context";
import { apiErrorMessage, downloadReport, projectsApi } from "@/lib/api-client";

export function ExportButtons({
  projectId,
  version,
  projectName,
}: {
  projectId: number;
  version: number;
  projectName: string;
}) {
  const [downloading, setDownloading] = useState<"excel" | "pdf" | null>(null);
  const { displayCurrency } = useCurrency();

  async function handleExport(kind: "excel" | "pdf") {
    setDownloading(kind);
    try {
      const url =
        kind === "excel"
          ? projectsApi.exportExcelUrl(projectId, version, displayCurrency)
          : projectsApi.exportPdfUrl(projectId, version, displayCurrency);
      const ext = kind === "excel" ? "xlsx" : "pdf";
      const filename = `${projectName.replace(/[^a-zA-Z0-9]+/g, "_")}_v${version}.${ext}`;
      // Renders the report in whatever currency is currently selected on
      // screen (see useCurrency()) - the backend converts every figure via
      // CurrencyConverter.convert_estimate before rendering, or falls back
      // to the estimate's native currency if a rate isn't available.
      await downloadReport(url, filename);
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
