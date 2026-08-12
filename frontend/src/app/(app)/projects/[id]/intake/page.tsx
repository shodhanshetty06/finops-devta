"use client";

import { Download, FileSpreadsheet, MessageSquareText } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage, intakeApi, projectsApi } from "@/lib/api-client";

function IntakeForms({ projectId }: { projectId: number }) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);

  const [projectName, setProjectName] = useState("");
  const [text, setText] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    try {
      const result = await projectsApi.createFromExcel(projectId, file);
      toast.success(`Estimate v${result.version} created from questionnaire`);
      router.push(`/projects/${projectId}/estimates/${result.version}`);
    } catch (err) {
      toast.error("Could not process the questionnaire", { description: apiErrorMessage(err) });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleTextExtract(e: React.FormEvent) {
    e.preventDefault();
    setIsExtracting(true);
    try {
      const result = await projectsApi.createFromText(projectId, { project_name: projectName, text });
      toast.success(`Estimate v${result.version} created from description`);
      router.push(`/projects/${projectId}/estimates/${result.version}`);
    } catch (err) {
      toast.error("Could not extract requirements", { description: apiErrorMessage(err) });
    } finally {
      setIsExtracting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Upload or describe your requirements</h1>
        <p className="text-sm text-muted-foreground">Either path creates a new version of this project.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
            Excel questionnaire
          </CardTitle>
          <CardDescription>Download the template, fill it in, then upload it here.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <a href={intakeApi.templateUrl()} download>
            <Button type="button" variant="outline">
              <Download className="h-4 w-4" />
              Download template
            </Button>
          </a>
          <Input ref={fileInputRef} type="file" accept=".xlsx" onChange={handleFileUpload} disabled={isUploading} className="max-w-sm" />
          {isUploading && <Spinner className="text-muted-foreground" />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquareText className="h-4 w-4 text-muted-foreground" />
            Describe it in plain language
          </CardTitle>
          <CardDescription>
            e.g. &ldquo;500 users, HA required, 99.99% uptime, 100GB database.&rdquo; The extractor will infer user
            counts, availability, database, and networking hints - every inference is shown as an assumption.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleTextExtract} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="project_name">Project name</Label>
              <Input id="project_name" required value={projectName} onChange={(e) => setProjectName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="text">Description</Label>
              <Textarea
                id="text"
                required
                rows={5}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Describe the workload, expected traffic, and any availability or compliance requirements..."
              />
            </div>
            <Button type="submit" disabled={isExtracting} className="self-start">
              {isExtracting && <Spinner />}
              Extract & estimate
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function IntakePage() {
  const params = useParams<{ id: string }>();
  return <IntakeForms projectId={Number(params.id)} />;
}
