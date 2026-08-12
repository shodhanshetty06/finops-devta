"use client";

import { FileSpreadsheet, FileText } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
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

  async function handleExport(kind: "excel" | "pdf") {
    setDownloading(kind);
    try {
      const url = kind === "excel" ? projectsApi.exportExcelUrl(projectId, version) : projectsApi.exportPdfUrl(projectId, version);
      const ext = kind === "excel" ? "xlsx" : "pdf";
      const filename = `${projectName.replace(/[^a-zA-Z0-9]+/g, "_")}_v${version}.${ext}`;
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
