"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogCloseButton, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { apiErrorMessage, projectsApi } from "@/lib/api-client";
import type { CustomerRequirement } from "@/lib/types";

const NEW_PROJECT_VALUE = "__new__";

/** Persists a statelessly-priced requirement (from New Estimate or the
 * standalone Questionnaire) as the first - or next - version of a real
 * project. Lets the user pick an existing project or create one inline,
 * rather than forcing them to leave and come back. */
export function SaveToProjectDialog({
  open,
  onOpenChange,
  requirement,
  commitmentTermYears,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  requirement: CustomerRequirement;
  commitmentTermYears: number;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list, enabled: open });
  const [selection, setSelection] = useState<string>(NEW_PROJECT_VALUE);
  const [newProjectName, setNewProjectName] = useState(requirement.project_name || "");
  const [isSaving, setIsSaving] = useState(false);

  async function handleSave() {
    setIsSaving(true);
    try {
      const projectId =
        selection === NEW_PROJECT_VALUE
          ? (await projectsApi.create(newProjectName.trim() || requirement.project_name)).id
          : Number(selection);

      const version = await projectsApi.createEstimateVersion(projectId, requirement, {
        force: true,
        commitmentTermYears,
      });
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success(`Saved as v${version.version}`);
      onOpenChange(false);
      router.push(`/projects/${projectId}/estimates/${version.version}`);
    } catch (err) {
      toast.error("Could not save to project", { description: apiErrorMessage(err) });
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Save to a project</DialogTitle>
          <DialogCloseButton onClick={() => onOpenChange(false)} />
        </DialogHeader>
        <DialogBody className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="project-select">Project</Label>
            <Select id="project-select" value={selection} onChange={(e) => setSelection(e.target.value)}>
              <option value={NEW_PROJECT_VALUE}>+ Create a new project</option>
              {projectsQuery.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
          {selection === NEW_PROJECT_VALUE && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="new-project-name">New project name</Label>
              <Input id="new-project-name" value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)} data-autofocus />
            </div>
          )}
        </DialogBody>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSave}
            disabled={isSaving || (selection === NEW_PROJECT_VALUE && !newProjectName.trim())}
          >
            {isSaving && <Spinner />}
            Save estimate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
