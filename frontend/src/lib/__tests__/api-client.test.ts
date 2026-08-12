import { AxiosError, AxiosHeaders } from "axios";
import { describe, expect, it } from "vitest";

import { apiErrorMessage } from "@/lib/api-client";

function makeAxiosError(status: number, body: unknown): AxiosError {
  const error = new AxiosError("Request failed", String(status), undefined, undefined, {
    status,
    statusText: "Error",
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
    data: body,
  });
  return error;
}

describe("apiErrorMessage", () => {
  it("extracts the message field from a FinOpsError response body", () => {
    const err = makeAxiosError(404, { error: "resource_not_found", message: "Project 5 not found." });
    expect(apiErrorMessage(err)).toBe("Project 5 not found.");
  });

  it("extracts the message field from a 422 validation-failure body with results", () => {
    const err = makeAxiosError(422, {
      error: "validation_failed",
      message: "Blocker-severity validation findings exist.",
      results: [{ field: "compute.vcpu", severity: "blocker" }],
    });
    expect(apiErrorMessage(err)).toBe("Blocker-severity validation findings exist.");
  });

  it("falls back to a generic Error's message for non-axios errors", () => {
    expect(apiErrorMessage(new Error("network down"))).toBe("network down");
  });

  it("falls back to a generic message for entirely unknown error shapes", () => {
    expect(apiErrorMessage("just a string")).toBe("An unexpected error occurred.");
  });
});
