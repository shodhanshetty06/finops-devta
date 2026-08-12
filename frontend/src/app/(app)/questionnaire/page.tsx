import { QuestionnaireWizard } from "@/components/wizard/questionnaire-wizard";

export default function QuestionnairePage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Questionnaire</h1>
        <p className="text-sm text-muted-foreground">
          Guided, step-by-step requirement intake. Prices immediately - save the result to a project once you&apos;re happy with it.
        </p>
      </div>
      <QuestionnaireWizard />
    </div>
  );
}
