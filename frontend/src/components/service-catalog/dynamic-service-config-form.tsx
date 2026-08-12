"use client";

// The one generic, schema-driven configuration form for every service in
// the GCP service catalog. Renders purely from `configuration_schema` -
// there is deliberately no `if (definition.service_id === "pubsub")`
// anywhere here or elsewhere in the app; a new catalog entry on the backend
// (app/catalog/service_definitions.py) gets a working form for free.
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import type { ConfigFieldSchema, GCPServiceDefinition } from "@/lib/types";

function Field({ field, children }: { field: ConfigFieldSchema; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={field.field_id}>
        {field.label}
        {field.unit ? <span className="text-muted-foreground"> ({field.unit})</span> : null}
      </Label>
      {children}
      {field.help_text && <p className="text-xs text-muted-foreground">{field.help_text}</p>}
    </div>
  );
}

// Groups consecutive fields that share the same `group` label into one
// section, so a catalog entry that lists e.g. "Region / Location" fields
// followed by "Scaling Constraints" fields renders as labeled sections
// instead of one flat list. Fields without a group (or a service with no
// grouping at all) fall into their own ungrouped section - same flat
// rendering as before.
function groupFields(fields: ConfigFieldSchema[]): { group: string | null; fields: ConfigFieldSchema[] }[] {
  const sections: { group: string | null; fields: ConfigFieldSchema[] }[] = [];
  for (const field of fields) {
    const group = field.group ?? null;
    const last = sections[sections.length - 1];
    if (last && last.group === group) {
      last.fields.push(field);
    } else {
      sections.push({ group, fields: [field] });
    }
  }
  return sections;
}

function ConfigFieldInput({
  field,
  value,
  setField,
}: {
  field: ConfigFieldSchema;
  value: unknown;
  setField: (fieldId: string, value: unknown) => void;
}) {
  if (field.field_type === "boolean") {
    return (
      <label className="flex items-center gap-2 text-sm sm:col-span-2">
        <Checkbox
          id={field.field_id}
          checked={Boolean(value)}
          onChange={(e) => setField(field.field_id, e.target.checked)}
        />
        {field.label}
      </label>
    );
  }

  if (field.field_type === "select") {
    return (
      <Field field={field}>
        <Select
          id={field.field_id}
          value={typeof value === "string" ? value : ""}
          onChange={(e) => setField(field.field_id, e.target.value)}
        >
          {!field.required && <option value="">-</option>}
          {(field.options ?? []).map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </Select>
      </Field>
    );
  }

  if (field.field_type === "number") {
    return (
      <Field field={field}>
        <Input
          id={field.field_id}
          type="number"
          min={field.min_value ?? undefined}
          max={field.max_value ?? undefined}
          value={typeof value === "number" ? value : (value as string) ?? ""}
          onChange={(e) => setField(field.field_id, e.target.value === "" ? null : Number(e.target.value))}
        />
      </Field>
    );
  }

  return (
    <Field field={field}>
      <Input
        id={field.field_id}
        type="text"
        value={typeof value === "string" ? value : ""}
        onChange={(e) => setField(field.field_id, e.target.value)}
      />
    </Field>
  );
}

export function DynamicServiceConfigForm({
  definition,
  config,
  onChange,
}: {
  definition: GCPServiceDefinition;
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}) {
  if (definition.configuration_schema.length === 0) {
    return <p className="text-xs text-muted-foreground">This service has no additional configuration.</p>;
  }

  function setField(fieldId: string, value: unknown) {
    onChange({ ...config, [fieldId]: value });
  }

  return (
    <div className="flex flex-col gap-4">
      {groupFields(definition.configuration_schema).map((section, i) => (
        <div key={section.group ?? `ungrouped-${i}`} className="flex flex-col gap-2">
          {section.group && <h4 className="text-xs font-medium text-muted-foreground">{section.group}</h4>}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {section.fields.map((field) => (
              <ConfigFieldInput key={field.field_id} field={field} value={config[field.field_id]} setField={setField} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
