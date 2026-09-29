export type OpportunityResumeTarget =
  | { kind: "open"; documentId: string }
  | { kind: "create" }
  | { kind: "unavailable" };

export function resolveOpportunityResume(input: {
  documentId?: string | null;
  phase: string;
  result: string;
  readOnly: boolean;
}): OpportunityResumeTarget {
  if (input.documentId) return { kind: "open", documentId: input.documentId };
  if (!input.readOnly && input.result === "active" && input.phase === "resume") {
    return { kind: "create" };
  }
  return { kind: "unavailable" };
}

export function resumeEditorHref(documentId: string, options: { submit?: boolean } = {}): string {
  const params = new URLSearchParams({ document_id: documentId });
  if (options.submit) params.set("submit", "1");
  return `/#resume?${params.toString()}`;
}

export function opportunityResumeHref(opportunityId: string): string {
  return `/#opportunities/${encodeURIComponent(opportunityId)}?tab=resume`;
}
