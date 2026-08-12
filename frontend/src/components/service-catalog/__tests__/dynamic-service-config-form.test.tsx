import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DynamicServiceConfigForm } from "@/components/service-catalog/dynamic-service-config-form";
import type { GCPServiceDefinition } from "@/lib/types";

const definition: GCPServiceDefinition = {
  service_id: "pubsub",
  display_name: "Pub/Sub",
  category: "Messaging & Eventing",
  description: "",
  icon: "send",
  configuration_schema: [
    { field_id: "messages_per_month", label: "Messages/month", field_type: "number", unit: "messages", default: 100_000_000, min_value: 0, max_value: null, options: null, required: true, help_text: null, group: null },
    { field_id: "engine", label: "Engine", field_type: "select", unit: null, default: "postgres", min_value: null, max_value: null, options: [{ value: "postgres", label: "PostgreSQL" }, { value: "mysql", label: "MySQL" }], required: true, help_text: null, group: null },
    { field_id: "high_availability", label: "High availability", field_type: "boolean", unit: null, default: false, min_value: null, max_value: null, options: null, required: false, help_text: null, group: null },
  ],
  pricing_dimensions: [],
  legacy_binding: null,
  active: true,
};

describe("DynamicServiceConfigForm", () => {
  it("renders one input per schema field, driven purely by field_type - no service-specific branching", () => {
    render(<DynamicServiceConfigForm definition={definition} config={{}} onChange={vi.fn()} />);
    expect(screen.getByLabelText(/Messages\/month/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Engine/)).toBeInTheDocument();
    expect(screen.getByText("High availability")).toBeInTheDocument();
  });

  it("calls onChange with the merged config when a number field changes", () => {
    const onChange = vi.fn();
    render(<DynamicServiceConfigForm definition={definition} config={{ engine: "postgres" }} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(/Messages\/month/), { target: { value: "50000000" } });
    expect(onChange).toHaveBeenCalledWith({ engine: "postgres", messages_per_month: 50000000 });
  });

  it("calls onChange when a select field changes", () => {
    const onChange = vi.fn();
    render(<DynamicServiceConfigForm definition={definition} config={{}} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(/Engine/), { target: { value: "mysql" } });
    expect(onChange).toHaveBeenCalledWith({ engine: "mysql" });
  });

  it("calls onChange when a boolean field is toggled", () => {
    const onChange = vi.fn();
    render(<DynamicServiceConfigForm definition={definition} config={{}} onChange={onChange} />);
    fireEvent.click(screen.getByText("High availability"));
    expect(onChange).toHaveBeenCalledWith({ high_availability: true });
  });

  it("renders a message instead of a form when the service has no configuration schema", () => {
    render(<DynamicServiceConfigForm definition={{ ...definition, configuration_schema: [] }} config={{}} onChange={vi.fn()} />);
    expect(screen.getByText(/no additional configuration/i)).toBeInTheDocument();
  });

  it("renders a subheading for fields that share a group, and no heading for ungrouped fields", () => {
    const grouped: GCPServiceDefinition = {
      ...definition,
      configuration_schema: [
        { field_id: "region", label: "Region", field_type: "select", unit: null, default: "us-central1", min_value: null, max_value: null, options: [{ value: "us-central1", label: "us-central1" }], required: false, help_text: null, group: "Region / Location" },
        { field_id: "nodes", label: "Nodes", field_type: "number", unit: null, default: 1, min_value: 1, max_value: null, options: null, required: true, help_text: null, group: null },
      ],
    };
    render(<DynamicServiceConfigForm definition={grouped} config={{}} onChange={vi.fn()} />);
    expect(screen.getByText("Region / Location")).toBeInTheDocument();
    expect(screen.getByLabelText(/Region/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Nodes/)).toBeInTheDocument();
  });
});
