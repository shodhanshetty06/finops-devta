"use client";

import { useParams } from "next/navigation";

import { QuestionnaireWizard } from "@/components/wizard/questionnaire-wizard";

export default function NewEstimatePage() {
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">New estimate</h1>
        <p className="text-sm text-muted-foreground">Answer the questionnaire to generate a priced, validated estimate.</p>
      </div>
      <QuestionnaireWizard projectId={projectId} />
    </div>
  );
}
